"""NeedBridge API. Uses only libraries already in your requirements.txt (starlette, uvicorn, pandas).

Run from C:\\Needbridge:   uvicorn backend.api:app --reload
Then open http://127.0.0.1:8000/api/needs
"""
import csv
import os
import shutil
from pathlib import Path
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from backend import relational_api

from backend import auth, matching
from backend.geo import AREAS, canonical_area, distance_km

CATEGORIES = {"notebooks", "school_bag", "textbooks", "geometry_box", "storybooks", "stationery"}
CONDITIONS = {"new", "good", "fair"}


# ---------- pure helpers (these are the parts we unit-test) ----------
def explain(m):
    """One honest sentence saying why a donation fits a request. `m` is a row of score_matches(detail=True)."""
    span = m["age_max_r"] - m["age_min_r"] + 1
    overlap = max(0, min(m["age_max_d"], m["age_max_r"]) - max(m["age_min_d"], m["age_min_r"]) + 1)
    parts = [f"same category ({m['category_d'].replace('_', ' ')})", f"fits {overlap} of {span} requested age years"]
    if m["area_d"] == m["area_r"]:
        parts.append(f"same area ({m['area_r']})")
    else:
        km = distance_km(canonical_area(m["area_d"]), canonical_area(m["area_r"]))
        parts.append(f"{m['area_d']} to {m['area_r']}, about {km:.1f} km")
    parts.append(f"condition: {m['condition']}")
    parts.append(f"covers {m['quantity']} of {m['quantity_needed']} needed")
    return "Good match: " + "; ".join(parts) + "."


def _int(v, lo, hi, label, errors):
    try:
        n = int(v)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a whole number.")
        return None
    if not lo <= n <= hi:
        errors.append(f"{label} must be between {lo} and {hi}.")
        return None
    return n


def _common(d, errors):
    row = {}
    row["category"] = d.get("category")
    if row["category"] not in CATEGORIES:
        errors.append("Choose a valid category.")
    row["item"] = str(d.get("item", "")).strip()
    if not 2 <= len(row["item"]) <= 60:
        errors.append("Item name must be 2 to 60 characters.")
    row["age_min"] = _int(d.get("age_min"), 3, 18, "Minimum age", errors)
    row["age_max"] = _int(d.get("age_max"), 3, 18, "Maximum age", errors)
    if row["age_min"] and row["age_max"] and row["age_min"] > row["age_max"]:
        errors.append("Minimum age cannot be above maximum age.")
    row["area"] = canonical_area(d.get("area", ""))
    if row["area"] is None:
        errors.append("Choose an area in Chhatrapati Sambhajinagar.")
    return row


def clean_donation(d):
    errors = []
    r = _common(d, errors)
    r["donor"] = str(d.get("donor", "")).strip()
    if not 2 <= len(r["donor"]) <= 60:
        errors.append("Donor name must be 2 to 60 characters.")
    r["quantity"] = _int(d.get("quantity"), 1, 500, "Quantity", errors)
    r["condition"] = d.get("condition")
    if r["condition"] not in CONDITIONS:
        errors.append("Condition must be new, good or fair.")
    cols = ["donor", "category", "item", "quantity", "condition", "age_min", "age_max", "area"]
    return {c: r[c] for c in cols}, errors


def clean_request(d):
    errors = []
    r = _common(d, errors)
    r["organization"] = str(d.get("organization", "")).strip()
    if not 2 <= len(r["organization"]) <= 60:
        errors.append("Organisation name must be 2 to 60 characters.")
    r["quantity_needed"] = _int(d.get("quantity_needed"), 1, 500, "Quantity needed", errors)
    r["verified"] = "no"  # new requests are never verified automatically
    cols = ["organization", "category", "item", "quantity_needed", "age_min", "age_max", "area", "verified"]
    return {c: r[c] for c in cols}, errors


def append_row(path, id_col, prefix, row):
    """Add a row to a CSV, creating the next id (D11, R09 ...). Handles files with no final newline."""
    with open(path, newline="", encoding="utf-8") as f:
        text = f.read()
    rows = list(csv.DictReader(text.splitlines()))
    nxt = max([int(r[id_col][1:]) for r in rows] + [0]) + 1
    new_id = f"{prefix}{nxt:02d}"
    with open(path, "a", newline="", encoding="utf-8") as f:
        if text and not text.endswith("\n"):
            f.write("\r\n")
        header = text.splitlines()[0].split(",")
        csv.DictWriter(f, fieldnames=header).writerow({id_col: new_id, **row})
    return new_id


# ---------- routes ----------
def engine(min_score=50):
    donations, requests = matching.load_data()
    matches = matching.score_matches(donations, requests, detail=True)
    plan, still = matching.allocate(matches, donations, requests, min_score)
    return donations, requests, matches, plan, still


async def health(request):
    return JSONResponse({"ok": True})


async def areas(request):
    return JSONResponse(list(AREAS))


async def needs(request):
    q = request.query_params
    me = canonical_area(q.get("area", "Kranti Chowk")) or "Kranti Chowk"
    _, requests, _, plan, still = engine()
    out = []
    for r in requests.itertuples():
        area = canonical_area(r.area)
        out.append({"id": r.request_id, "organization": r.organization, "item": r.item, "category": r.category,
                    "area": r.area, "age_min": int(r.age_min), "age_max": int(r.age_max),
                    "needed": int(r.quantity_needed), "remaining": int(still[r.request_id]),
                    "fulfilled": int(r.quantity_needed - still[r.request_id]),
                    "distance_km": round(distance_km(me, area), 1) if area else None})
    if q.get("category"):
        out = [n for n in out if n["category"] == q["category"]]
    if q.get("q"):
        needle = q["q"].lower()
        out = [n for n in out if needle in f"{n['item']} {n['organization']} {n['area']}".lower()]
    return JSONResponse(sorted(out, key=lambda n: (n["distance_km"] is None, n["distance_km"])))


async def matches(request):
    min_score = float(request.query_params.get("min_score", 50))
    _, _, scored, plan, _ = engine(min_score)
    detail = {(m.donation_id, m.request_id): m._asdict() for m in scored.itertuples()}
    rows = []
    for p in plan.itertuples():
        rows.append({"donation": p.donation, "request": p.request, "organization": p.organization,
                     "items": int(p.items), "score": float(p.score), "why": explain(detail[(p.donation, p.request)])})
    return JSONResponse(rows)


async def dashboard(request):
    _, reqs, _, plan, still = engine()
    total = int(reqs["quantity_needed"].sum())
    matched = int(plan["items"].sum()) if len(plan) else 0
    return JSONResponse({"verified_requests": len(reqs), "items_matched": matched,
                         "items_still_needed": int(sum(still.values())), "needs_fulfilled_pct": round(100 * matched / total)})


async def _post(request, cleaner, filename, id_col, prefix, override):
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"errors": ["Send JSON."]}, status_code=400)
    body.update(override)  # the name always comes from the logged-in account, never from the form
    row, errors = cleaner(body)
    if errors:
        return JSONResponse({"errors": errors}, status_code=422)
    return JSONResponse({"id": append_row(matching.DATA_DIR / filename, id_col, prefix, row)}, status_code=201)


async def add_donation(request):
    user, denied = auth.require(request, "donor")
    if denied:
        return denied
    return await _post(request, clean_donation, "donations.csv", "donation_id", "D", {"donor": user["name"]})


async def add_request(request):
    user, denied = auth.require(request, "org")
    if denied:
        return denied
    return await _post(request, clean_request, "requests.csv", "request_id", "R", {"organization": user["name"]})

# ---------- admin: review new requests ----------
def set_verified(path, request_id, value):
    """Change the 'verified' column of one request. Returns True if that request exists."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    found = False
    for r in rows:
        if r["request_id"] == request_id:
            r["verified"], found = value, True
    if found:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return found


async def admin_pending(request):
    _, denied = auth.require(request, "admin")
    if denied:
        return denied
    with open(matching.DATA_DIR / "requests.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return JSONResponse([r for r in rows if r["verified"] not in ("yes", "rejected")])


async def admin_review(request):
    _, denied = auth.require(request, "admin")
    if denied:
        return denied
    try:
        action = (await request.json()).get("action")
    except ValueError:
        action = None
    if action not in ("approve", "reject"):
        return JSONResponse({"errors": ["Action must be approve or reject."]}, status_code=422)
    rid = request.path_params["rid"]
    if not set_verified(matching.DATA_DIR / "requests.csv", rid, "yes" if action == "approve" else "rejected"):
        return JSONResponse({"errors": ["Request not found."]}, status_code=404)
    return JSONResponse({"id": rid, "verified": action == "approve"})


# ---------- start-up: fresh server disk, first admin, secret key ----------
ROOT = Path(__file__).resolve().parent.parent


def seed_data():
    """On a brand-new server disk, copy the sample CSV files in so the site is not empty."""
    target = matching.DATA_DIR
    target.mkdir(parents=True, exist_ok=True)
    for name in ("donations.csv", "requests.csv"):
        if not (target / name).exists() and (ROOT / "data" / name).exists():
            shutil.copy(ROOT / "data" / name, target / name)


def ensure_admin():
    """If ADMIN_EMAIL and ADMIN_PASSWORD are set, make sure that admin account exists."""
    email, password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if email and password and not auth.check_login(email, password):
        auth.create_user(os.environ.get("ADMIN_NAME", "Admin"), email, password, "admin", allow_admin=True)


seed_data()
ensure_admin()

# Local development has a fallback; production must supply its own long random secret.
if os.environ.get("APP_ENV", "development").lower() == "production":
    if not os.environ.get("NEEDBRIDGE_SECRET"):
        raise RuntimeError("NEEDBRIDGE_SECRET must be set in production.")
    if relational_api.storage.BACKEND != "s3" and os.environ.get("NEEDBRIDGE_PERSISTENT_UPLOADS") != "1":
        raise RuntimeError("Production uploads need S3-compatible storage, or an explicitly mounted persistent disk with NEEDBRIDGE_PERSISTENT_UPLOADS=1.")
SECRET = os.environ.get("NEEDBRIDGE_SECRET", "dev-only-secret-change-me")
DIST = ROOT / "frontend" / "dist"

routes = [
    Route("/api/health", health), Route("/api/areas", areas), Route("/api/needs", needs),
    Route("/api/matches", matches), Route("/api/dashboard", dashboard),
    Route("/api/donations", add_donation, methods=["POST"]), Route("/api/requests", add_request, methods=["POST"]),
    Route("/api/auth/signup", auth.signup, methods=["POST"]), Route("/api/auth/login", auth.login, methods=["POST"]),
    Route("/api/auth/logout", auth.logout, methods=["POST"]), Route("/api/auth/me", auth.me),
    Route("/api/admin/requests", admin_pending), Route("/api/admin/requests/{rid}", admin_review, methods=["POST"]),
    # Relational API v2: kept alongside legacy routes during the migration.
    Route("/api/v2/auth/signup", relational_api.signup, methods=["POST"]),
    Route("/api/v2/auth/login", relational_api.login, methods=["POST"]),
    Route("/api/v2/auth/logout", relational_api.logout, methods=["POST"]),
    Route("/api/v2/auth/me", relational_api.me),
    Route("/api/v2/profile", relational_api.profile),
    Route("/api/v2/profile", relational_api.update_profile, methods=["PATCH"]),
    Route("/api/v2/admin/accounts", relational_api.admin_accounts),
    Route("/api/v2/admin/accounts/{user_id}/status", relational_api.admin_set_account_status, methods=["POST"]),
    Route("/api/v2/dashboard", relational_api.dashboard),
    Route("/api/v2/categories", relational_api.categories),
    Route("/api/v2/donations", relational_api.list_donations),
    Route("/api/v2/donations", relational_api.create_donation, methods=["POST"]),
    Route("/api/v2/requirements", relational_api.list_requirements),
    Route("/api/v2/requirements", relational_api.create_requirement, methods=["POST"]),
    Route("/api/v2/my-listings", relational_api.my_listings),
    Route("/api/v2/reports", relational_api.create_report, methods=["POST"]),
    Route("/api/v2/admin/reports", relational_api.admin_reports),
    Route("/api/v2/admin/reports/{report_id}", relational_api.admin_review_report, methods=["POST"]),
    Route("/api/v2/listings/{kind:str}/{listing_id:str}/activity", relational_api.listing_activity),
    Route("/api/v2/listings/{kind:str}/{listing_id:str}", relational_api.update_listing, methods=["PATCH"]),
    Route("/api/v2/listings/{kind:str}/{listing_id:str}/status", relational_api.change_listing_status, methods=["POST"]),
    Route("/api/v2/matches", relational_api.matches),
    Route("/api/v2/offers", relational_api.list_offers),
    Route("/api/v2/offers", relational_api.create_offer, methods=["POST"]),
    Route("/api/v2/offers/{offer_id}/respond", relational_api.respond_offer, methods=["POST"]),
    Route("/api/v2/offers/{offer_id}/contacts", relational_api.offer_contacts),
    Route("/api/v2/handovers/{handover_id}/schedule", relational_api.schedule_handover, methods=["POST"]),
    Route("/api/v2/handovers/{handover_id}/confirm", relational_api.confirm_handover, methods=["POST"]),
    Route("/api/v2/handovers/{handover_id}/cancel", relational_api.cancel_handover, methods=["POST"]),
    Route("/api/v2/notifications", relational_api.inbox),
    Route("/api/v2/notifications/read-all", relational_api.mark_all_notifications_read, methods=["POST"]),
    Route("/api/v2/notifications/{notification_id}/read", relational_api.mark_notification_read, methods=["POST"]),
    Route("/api/v2/admin/organisations", relational_api.admin_pending_organisations),
    Route("/api/v2/admin/organisations/{organisation_id}", relational_api.admin_review_organisation, methods=["POST"]),
    Route("/api/v2/admin/verification-documents/{document_id}", relational_api.admin_review_verification_document, methods=["POST"]),
    Route("/api/v2/donations/{donation_id}/photos", relational_api.upload_donation_photo, methods=["POST"]),
    Route("/api/v2/organisations/{organisation_id}/verification-documents", relational_api.upload_verification_document, methods=["POST"]),
    Route("/api/v2/files/{file_id}", relational_api.serve_file),
]
if DIST.exists():  # after `npm run build` the Python server also serves the website itself
    routes.append(Mount("/", app=StaticFiles(directory=DIST, html=True), name="site"))

app = Starlette(
    routes=routes,
    middleware=[Middleware(SessionMiddleware, secret_key=SECRET, max_age=14 * 24 * 3600, same_site="lax",
                           https_only=os.environ.get("NEEDBRIDGE_HTTPS") == "1")],
)
