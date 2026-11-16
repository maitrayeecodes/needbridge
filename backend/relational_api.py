"""PostgreSQL-backed NeedBridge API (v2).

The existing CSV/SQLite API remains available during migration. New workflows use
SQLAlchemy and the relational schema; once the frontend is migrated, legacy routes
can be retired safely.
"""
from __future__ import annotations

import os
from uuid import UUID
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_, and_, func
from sqlalchemy.exc import IntegrityError
from starlette.responses import JSONResponse, Response, RedirectResponse

from backend.database import get_session_factory
from backend.models import (User, Organisation, OrganisationMember, Category, Donation,
    Requirement, MatchSuggestion, Offer, Handover, HandoverConfirmation, AuditLog, Notification,
    StoredFile, DonationPhoto, VerificationDocument, Report)
from backend import storage
from backend.auth import hash_password, verify_password, EMAIL
from backend.geo import canonical_area, distance_km


def _json_error(message, status=400):
    return JSONResponse({"errors": [message]}, status_code=status)


def _body(request):
    return request.json()


def _uid(request):
    value = request.session.get("v2_uid")
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _current(db, request):
    uid = _uid(request)
    return db.get(User, uid) if uid else None


def _require(db, request, *roles):
    user = _current(db, request)
    if not user or not user.is_active:
        return None, _json_error("Please log in first.", 401)
    if roles and user.role not in roles:
        return None, _json_error("You do not have permission to perform this action.", 403)
    return user, None


def _audit(db, actor, action, entity_type, entity_id, details=None):
    import json
    db.add(AuditLog(actor_user_id=actor.id if actor else None, action=action,
        entity_type=entity_type, entity_id=str(entity_id),
        details=json.dumps(details, ensure_ascii=False) if details else None))


def _notify(db, user_id, kind, title, body, target_type=None, target_id=None):
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body,
        target_type=target_type, target_id=str(target_id) if target_id else None))


def _public_user(user):
    return {"id": str(user.id), "name": user.name, "email": user.email, "role": user.role}


def _public_donation(d, category):
    return {"id": str(d.id), "title": d.title, "description": d.description,
        "category": category.label, "condition": d.condition, "age_min": d.age_min,
        "age_max": d.age_max, "area": d.area, "quantity_total": d.quantity_total,
        "quantity_available": d.quantity_total-d.quantity_reserved-d.quantity_donated,
        "status": d.status, "created_at": d.created_at.isoformat()}


def _public_requirement(r, category, org, near_area=None):
    remaining = r.quantity_requested-r.quantity_reserved-r.quantity_fulfilled
    distance = None
    if near_area:
        try: distance = round(distance_km(near_area, r.area), 1)
        except KeyError: distance = None
    return {"id": str(r.id), "title": r.title, "item": r.title, "description": r.description,
        "category": category.slug, "category_label": category.label, "category_slug": category.slug,
        "age_min": r.age_min if r.age_min is not None else 3,
        "age_max": r.age_max if r.age_max is not None else 18,
        "area": r.area, "organisation": org.name, "organization": org.name,
        "quantity_requested": r.quantity_requested, "needed": r.quantity_requested,
        "fulfilled": r.quantity_fulfilled, "remaining": remaining,
        "quantity_available": remaining, "distance_km": distance,
        "status": r.status, "created_at": r.created_at.isoformat()}

async def signup(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    name, email, password, role = (str(b.get(k) or "").strip() for k in ("name", "email", "password", "role"))
    email = email.lower()
    if not 2 <= len(name) <= 100: return _json_error("Name must be 2 to 100 characters.", 422)
    if not EMAIL.match(email): return _json_error("Enter a valid email address.", 422)
    if len(password) < 8: return _json_error("Password must be at least 8 characters.", 422)
    if role not in {"donor", "org_member"}: return _json_error("Choose donor or school/NGO.", 422)
    db = get_session_factory()()
    try:
        if db.scalar(select(User.id).where(User.email == email)):
            return _json_error("An account with this email already exists.", 409)
        user = User(name=name, email=email, password_hash=hash_password(password), role=role)
        db.add(user); db.flush()
        if role == "org_member":
            org_name = str(b.get("organisation_name") or "").strip()
            org_type = str(b.get("organisation_type") or "school").strip()
            area = canonical_area(b.get("area"))
            if not 2 <= len(org_name) <= 160 or org_type not in {"school", "ngo", "community_group", "other"} or not area:
                db.rollback(); return _json_error("For institution registration, provide its name, type and a valid service area.", 422)
            org = Organisation(name=org_name, organisation_type=org_type,
                description=str(b.get("organisation_description") or "").strip() or None,
                public_area=area, private_address=str(b.get("private_address") or "").strip() or None,
                contact_phone=str(b.get("phone") or "").strip() or None, verification_status="pending")
            db.add(org); db.flush()
            db.add(OrganisationMember(organisation_id=org.id, user_id=user.id, member_role="owner"))
        db.commit(); request.session["v2_uid"] = str(user.id)
        public = _public_user(user)
        if role == "org_member":
            public["organisation"] = {"id": str(org.id), "name": org.name,
                "verification_status": org.verification_status, "area": org.public_area,
                "member_role": "owner"}
        return JSONResponse(public, status_code=201)
    except IntegrityError:
        db.rollback(); return _json_error("An account with this email already exists.", 409)
    finally: db.close()


async def login(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user = db.scalar(select(User).where(User.email == str(b.get("email") or "").strip().lower()))
        if not user or not user.is_active or not verify_password(str(b.get("password") or ""), user.password_hash):
            return _json_error("Wrong email or password.", 401)
        request.session["v2_uid"] = str(user.id)
        return JSONResponse(_public_user(user))
    finally: db.close()


async def logout(request):
    request.session.pop("v2_uid", None)
    return JSONResponse({"ok": True})


async def me(request):
    db = get_session_factory()()
    try:
        user = _current(db, request)
        if not user or not user.is_active:
            request.session.pop("v2_uid", None)
            return JSONResponse(None)
        data = _public_user(user)
        if user.role == "org_member":
            row = db.execute(select(Organisation, OrganisationMember.member_role).join(OrganisationMember).where(OrganisationMember.user_id == user.id)).first()
            if row:
                org, member_role = row
                data["organisation"] = {"id": str(org.id), "name": org.name,
                    "verification_status": org.verification_status, "area": org.public_area,
                    "member_role": member_role}
        return JSONResponse(data)
    finally: db.close()


async def categories(request):
    db = get_session_factory()()
    try:
        rows = db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.label)).all()
        return JSONResponse([{"id": x.id, "slug": x.slug, "label": x.label} for x in rows])
    finally: db.close()


async def create_donation(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor")
        if denied: return denied
        category = db.get(Category, b.get("category_id"))
        area = canonical_area(b.get("area"))
        title = str(b.get("title") or "").strip()
        condition = b.get("condition")
        try: qty = int(b.get("quantity_total"))
        except (ValueError, TypeError): qty = 0
        if not category or not title or len(title) > 120 or not area or condition not in {"new", "good", "fair"} or qty < 1:
            return _json_error("Provide a title, valid category, condition, area and positive quantity.", 422)
        age_min, age_max = b.get("age_min"), b.get("age_max")
        if age_min is not None and (not isinstance(age_min, int) or not 3 <= age_min <= 18): return _json_error("Minimum age must be between 3 and 18.", 422)
        if age_max is not None and (not isinstance(age_max, int) or not 3 <= age_max <= 18): return _json_error("Maximum age must be between 3 and 18.", 422)
        if age_min is not None and age_max is not None and age_min > age_max: return _json_error("Minimum age cannot exceed maximum age.", 422)
        item = Donation(donor_id=user.id, category_id=category.id, title=title,
            description=str(b.get("description") or "").strip() or None, condition=condition,
            age_min=age_min, age_max=age_max, area=area, quantity_total=qty, status="active")
        db.add(item); db.flush(); _audit(db, user, "donation.created", "donation", item.id)
        db.commit()
        return JSONResponse(_public_donation(item, category), status_code=201)
    finally: db.close()


async def create_requirement(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "org_member")
        if denied: return denied
        org = db.scalar(select(Organisation).join(OrganisationMember).where(OrganisationMember.user_id == user.id))
        if not org: return _json_error("Your account is not linked to an institution.", 403)
        if org.verification_status != "verified": return _json_error("Your institution must be verified before publishing requirements.", 403)
        category = db.get(Category, b.get("category_id")); area = canonical_area(b.get("area") or org.public_area)
        title = str(b.get("title") or "").strip()
        try: qty = int(b.get("quantity_requested"))
        except (ValueError, TypeError): qty = 0
        if not category or not title or len(title) > 120 or not area or qty < 1:
            return _json_error("Provide a title, valid category, area and positive quantity.", 422)
        age_min, age_max = b.get("age_min"), b.get("age_max")
        if age_min is not None and (not isinstance(age_min, int) or not 3 <= age_min <= 18): return _json_error("Minimum age must be between 3 and 18.", 422)
        if age_max is not None and (not isinstance(age_max, int) or not 3 <= age_max <= 18): return _json_error("Maximum age must be between 3 and 18.", 422)
        if age_min is not None and age_max is not None and age_min > age_max: return _json_error("Minimum age cannot exceed maximum age.", 422)
        item = Requirement(organisation_id=org.id, created_by_user_id=user.id,
            category_id=category.id, title=title, description=str(b.get("description") or "").strip() or None,
            age_min=age_min, age_max=age_max, area=area, quantity_requested=qty, status="open")
        db.add(item); db.flush(); _audit(db, user, "requirement.created", "requirement", item.id)
        db.commit()
        return JSONResponse(_public_requirement(item, category, org), status_code=201)
    finally: db.close()


async def list_donations(request):
    db = get_session_factory()()
    try:
        stmt = select(Donation, Category).join(Category).where(Donation.status.in_(["active", "partially_fulfilled", "fully_reserved"]))
        if request.query_params.get("area"):
            area = canonical_area(request.query_params["area"])
            if not area: return _json_error("Unknown area.", 422)
            stmt = stmt.where(Donation.area == area)
        if request.query_params.get("category_id"):
            stmt = stmt.where(Donation.category_id == int(request.query_params["category_id"]))
        rows = db.execute(stmt.order_by(Donation.created_at.desc()).limit(100)).all()
        output = []
        for d, c in rows:
            if d.quantity_total <= d.quantity_reserved+d.quantity_donated: continue
            item = _public_donation(d, c)
            photos = db.execute(select(DonationPhoto, StoredFile).join(
                StoredFile, DonationPhoto.stored_file_id == StoredFile.id).where(
                DonationPhoto.donation_id == d.id).order_by(DonationPhoto.display_order)).all()
            item["photos"] = [f"/api/v2/files/{file.id}" for _, file in photos]
            output.append(item)
        return JSONResponse(output)
    finally: db.close()


async def list_requirements(request):
    db = get_session_factory()()
    try:
        stmt = select(Requirement, Category, Organisation).join(Category).join(Organisation).where(
            Requirement.status.in_(["open", "partially_fulfilled"]), Organisation.verification_status == "verified")
        if request.query_params.get("area"):
            area = canonical_area(request.query_params["area"])
            if not area: return _json_error("Unknown area.", 422)
            stmt = stmt.where(Requirement.area == area)
        if request.query_params.get("category_slug"):
            stmt = stmt.where(Category.slug == request.query_params["category_slug"])
        if request.query_params.get("category_id"):
            try: category_id = int(request.query_params["category_id"])
            except ValueError: return _json_error("Invalid category ID.", 422)
            stmt = stmt.where(Requirement.category_id == category_id)
        near_area = canonical_area(request.query_params.get("near_area")) if request.query_params.get("near_area") else None
        if request.query_params.get("near_area") and not near_area:
            return _json_error("Unknown reference area.", 422)
        rows = db.execute(stmt.order_by(Requirement.created_at.desc()).limit(100)).all()
        return JSONResponse([_public_requirement(r, c, o, near_area) for r, c, o in rows
            if r.quantity_requested > r.quantity_reserved+r.quantity_fulfilled])
    finally: db.close()

def _overlap(a_min, a_max, b_min, b_max):
    lo1, hi1 = a_min or 3, a_max or 18
    lo2, hi2 = b_min or 3, b_max or 18
    return max(lo1, lo2) <= min(hi1, hi2)


def _score(d, r):
    points, reasons = 0, []
    if d.category_id != r.category_id: return 0, []
    points += 40; reasons.append("Same resource category")
    if _overlap(d.age_min, d.age_max, r.age_min, r.age_max): points += 20; reasons.append("Suitable age range")
    try: km = distance_km(d.area, r.area)
    except KeyError: km = 99
    geo_points = max(0, round(20 * (1 - km / 30)))
    points += geo_points
    if km < 1: reasons.append("Same neighbourhood")
    elif km <= 10: reasons.append(f"Nearby areas (~{km:.1f} km straight-line)")
    elif geo_points: reasons.append("Within local service radius")
    condition_points = {"new": 10, "good": 8, "fair": 4}.get(d.condition, 0)
    points += condition_points; reasons.append(f"Item condition: {d.condition}")
    available = d.quantity_total-d.quantity_reserved-d.quantity_donated
    needed = r.quantity_requested-r.quantity_reserved-r.quantity_fulfilled
    if available > 0 and needed > 0:
        points += min(10, round(10 * min(available, needed) / max(available, needed)))
        reasons.append("Quantity can help meet the need")
    return min(100, points), reasons


async def matches(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        stmt = select(Donation, Requirement).join(Requirement, Donation.category_id == Requirement.category_id).join(
            Organisation, Requirement.organisation_id == Organisation.id).where(
            Donation.status.in_(["active", "partially_fulfilled"]),
            Requirement.status.in_(["open", "partially_fulfilled"]), Organisation.verification_status == "verified")
        if user.role == "donor": stmt = stmt.where(Donation.donor_id == user.id)
        else:
            org_id = db.scalar(select(OrganisationMember.organisation_id).where(OrganisationMember.user_id == user.id))
            if not org_id: return _json_error("Institution membership not found.", 403)
            stmt = stmt.where(Requirement.organisation_id == org_id)
        output = []
        for d, r in db.execute(stmt.limit(500)).all():
            if d.quantity_total <= d.quantity_reserved+d.quantity_donated or r.quantity_requested <= r.quantity_reserved+r.quantity_fulfilled: continue
            score, reasons = _score(d, r)
            if score >= 50:
                output.append({"donation": str(d.id), "requirement": str(r.id), "score": score,
                    "reasons": reasons, "donation_title": d.title, "requirement_title": r.title,
                    "donation_area": d.area, "requirement_area": r.area,
                    "available": d.quantity_total-d.quantity_reserved-d.quantity_donated,
                    "needed": r.quantity_requested-r.quantity_reserved-r.quantity_fulfilled})
        output.sort(key=lambda x: (-x["score"], x["donation_title"]))
        return JSONResponse(output[:100])
    finally: db.close()


async def create_offer(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        try: donation_id, requirement_id = UUID(str(b.get("donation_id"))), UUID(str(b.get("requirement_id")))
        except (ValueError, TypeError): return _json_error("Valid donation_id and requirement_id are required.", 422)
        d, r = db.get(Donation, donation_id), db.get(Requirement, requirement_id)
        if not d or not r: return _json_error("Donation or requirement not found.", 404)
        org = db.get(Organisation, r.organisation_id)
        if org.verification_status != "verified": return _json_error("Institution is not verified.", 403)
        if d.category_id != r.category_id: return _json_error("Donation and requirement categories do not match.", 422)
        if user.role == "donor":
            if d.donor_id != user.id: return _json_error("You can only offer your own donations.", 403)
            recipient = db.scalar(select(User).join(OrganisationMember).where(OrganisationMember.organisation_id == org.id, OrganisationMember.member_role == "owner"))
            if not recipient: return _json_error("Institution has no active account owner.", 409)
        else:
            member = db.scalar(select(OrganisationMember).where(OrganisationMember.user_id == user.id, OrganisationMember.organisation_id == org.id))
            if not member: return _json_error("You can only invite donors for your institution's requirements.", 403)
            recipient = db.get(User, d.donor_id)
        if recipient.id == user.id: return _json_error("You cannot send an offer to yourself.", 422)
        available = min(d.quantity_total-d.quantity_reserved-d.quantity_donated,
                        r.quantity_requested-r.quantity_reserved-r.quantity_fulfilled)
        try: qty = int(b.get("quantity", available))
        except (ValueError, TypeError): qty = 0
        if qty < 1 or qty > available: return _json_error(f"Quantity must be between 1 and {available}.", 422)
        existing = db.scalar(select(Offer).where(Offer.donation_id == d.id, Offer.requirement_id == r.id, Offer.status.in_(["pending", "accepted"])))
        if existing: return _json_error("An active offer already exists for this donation and requirement.", 409)
        offer = Offer(donation_id=d.id, requirement_id=r.id, initiated_by_user_id=user.id,
            recipient_user_id=recipient.id, quantity=qty, message=str(b.get("message") or "").strip() or None,
            status="pending", expires_at=datetime.now(timezone.utc)+timedelta(days=14))
        db.add(offer); db.flush()
        _notify(db, recipient.id, "offer_received", "New donation offer", f"{user.name} sent you a donation offer for {qty} item(s).", "offer", offer.id)
        _audit(db, user, "offer.created", "offer", offer.id, {"quantity": qty})
        db.commit()
        return JSONResponse({"id": str(offer.id), "status": offer.status, "quantity": offer.quantity, "recipient_user_id": str(recipient.id)}, status_code=201)
    finally: db.close()


async def respond_offer(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        try: oid = UUID(request.path_params["offer_id"])
        except ValueError: return _json_error("Invalid offer ID.", 422)
        # FOR UPDATE serialises competing acceptances on PostgreSQL.
        offer = db.scalar(select(Offer).where(Offer.id == oid).with_for_update())
        if not offer: return _json_error("Offer not found.", 404)
        if offer.recipient_user_id != user.id: return _json_error("Only the invited recipient can respond.", 403)
        if offer.status != "pending": return _json_error("This offer is no longer pending.", 409)
        action = b.get("action")
        if action == "decline":
            offer.status = "declined"; offer.responded_at = datetime.now(timezone.utc)
            _notify(db, offer.initiated_by_user_id, "offer_declined", "Offer declined",
                "The other participant declined your donation offer.", "offer", offer.id)
            _audit(db, user, "offer.declined", "offer", offer.id)
            db.commit(); return JSONResponse({"id": str(offer.id), "status": offer.status})
        if action != "accept": return _json_error("Action must be accept or decline.", 422)
        d = db.scalar(select(Donation).where(Donation.id == offer.donation_id).with_for_update())
        r = db.scalar(select(Requirement).where(Requirement.id == offer.requirement_id).with_for_update())
        if not d or not r: return _json_error("Related listing no longer exists.", 409)
        donor_left = d.quantity_total-d.quantity_reserved-d.quantity_donated
        need_left = r.quantity_requested-r.quantity_reserved-r.quantity_fulfilled
        if offer.quantity > min(donor_left, need_left): return _json_error("The available quantity has changed. Please create a new offer.", 409)
        d.quantity_reserved += offer.quantity; r.quantity_reserved += offer.quantity
        offer.status = "accepted"; offer.responded_at = datetime.now(timezone.utc)
        d.status = "fully_reserved" if d.quantity_total == d.quantity_reserved+d.quantity_donated else "partially_fulfilled"
        r.status = "partially_fulfilled"
        handover = Handover(offer_id=offer.id, quantity_agreed=offer.quantity, status="proposed")
        db.add(handover); db.flush()
        _notify(db, offer.initiated_by_user_id, "offer_accepted", "Offer accepted", "Your donation offer was accepted. Coordinate the handover.", "handover", handover.id)
        _audit(db, user, "offer.accepted", "offer", offer.id, {"quantity": offer.quantity})
        db.commit()
        return JSONResponse({"id": str(offer.id), "status": offer.status, "handover_id": str(handover.id), "quantity_reserved": offer.quantity})
    finally: db.close()


async def confirm_handover(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        try: hid = UUID(request.path_params["handover_id"])
        except ValueError: return _json_error("Invalid handover ID.", 422)
        h = db.scalar(select(Handover).where(Handover.id == hid).with_for_update())
        if not h: return _json_error("Handover not found.", 404)
        offer = db.get(Offer, h.offer_id); d = db.get(Donation, offer.donation_id); r = db.get(Requirement, offer.requirement_id)
        is_donor = user.id == d.donor_id
        is_institution_member = db.scalar(select(OrganisationMember.organisation_id).where(
            OrganisationMember.organisation_id == r.organisation_id,
            OrganisationMember.user_id == user.id)) is not None
        if not (is_donor or is_institution_member): return _json_error("You are not a participant in this handover.", 403)
        # Confirmation roles describe the real-world parties, not who initiated the offer.
        party = "donor" if is_donor else "recipient"
        try: qty = int(b.get("quantity_received", h.quantity_agreed))
        except (ValueError, TypeError): qty = -1
        if qty < 0 or qty > h.quantity_agreed: return _json_error("Confirmed quantity must be between zero and the agreed quantity.", 422)
        if db.scalar(select(HandoverConfirmation.id).where(HandoverConfirmation.handover_id == h.id, HandoverConfirmation.party == party)):
            return _json_error("You have already confirmed this handover.", 409)
        db.add(HandoverConfirmation(handover_id=h.id, confirmed_by_user_id=user.id, party=party,
            quantity_confirmed=qty, note=str(b.get("note") or "").strip() or None))
        db.flush()
        confirmations = db.scalars(select(HandoverConfirmation).where(HandoverConfirmation.handover_id == h.id)).all()
        if len(confirmations) == 2:
            if confirmations[0].quantity_confirmed != confirmations[1].quantity_confirmed:
                h.status = "disputed"
            else:
                received = confirmations[0].quantity_confirmed
                h.quantity_received = received
                # Release the full reservation, then count only mutually confirmed receipt.
                d.quantity_reserved -= h.quantity_agreed; d.quantity_donated += received
                r.quantity_reserved -= h.quantity_agreed; r.quantity_fulfilled += received
                h.status = "completed" if received == h.quantity_agreed else "partially_completed"
                offer.status = "completed"
                h.completed_at = datetime.now(timezone.utc)
                d.status = "completed" if d.quantity_donated == d.quantity_total else ("active" if d.quantity_total > d.quantity_donated+d.quantity_reserved else "fully_reserved")
                r.status = "fulfilled" if r.quantity_fulfilled == r.quantity_requested else ("open" if r.quantity_fulfilled+r.quantity_reserved == 0 else "partially_fulfilled")
        else:
            h.status = "awaiting_confirmation"
        other_user_id = offer.recipient_user_id if user.id == offer.initiated_by_user_id else offer.initiated_by_user_id
        notice_title = "Handover needs review" if h.status == "disputed" else "Handover confirmation received"
        notice_body = ("The two handover quantities do not match. NeedBridge support may need to review this." if h.status == "disputed"
            else "The other participant has confirmed the handover." if h.status in {"completed", "partially_completed"}
            else "One participant has confirmed the handover. Please confirm the quantity you received.")
        _notify(db, other_user_id, "handover_confirmation", notice_title, notice_body, "handover", h.id)
        _audit(db, user, "handover.confirmed", "handover", h.id, {"party": party, "quantity": qty})
        db.commit()
        return JSONResponse({"id": str(h.id), "status": h.status, "confirmations_received": len(confirmations), "quantity_received": h.quantity_received})
    finally: db.close()



async def dashboard(request):
    """Return role-scoped dashboard metrics; never expose another account's records."""
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member", "admin")
        if denied: return denied
        unread = db.scalar(select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
        if user.role == "admin":
            return JSONResponse({"role": "admin", "metrics": {
                "pending_organisations": db.scalar(select(func.count(Organisation.id)).where(
                    Organisation.verification_status.in_(["pending", "under_review"]))) or 0,
                "verified_organisations": db.scalar(select(func.count(Organisation.id)).where(
                    Organisation.verification_status == "verified")) or 0,
                "open_disputes": db.scalar(select(func.count(Handover.id)).where(
                    Handover.status == "disputed")) or 0,
                "unread_notifications": unread,
            }})
        if user.role == "donor":
            donation_count = db.scalar(select(func.count(Donation.id)).where(Donation.donor_id == user.id)) or 0
            active_count = db.scalar(select(func.count(Donation.id)).where(
                Donation.donor_id == user.id, Donation.status.in_(["active", "partially_fulfilled", "fully_reserved"]))) or 0
            available = db.scalar(select(func.coalesce(func.sum(
                Donation.quantity_total - Donation.quantity_reserved - Donation.quantity_donated), 0)).where(
                Donation.donor_id == user.id)) or 0
            donated = db.scalar(select(func.coalesce(func.sum(Donation.quantity_donated), 0)).where(
                Donation.donor_id == user.id)) or 0
            outgoing = db.scalar(select(func.count(Offer.id)).where(Offer.initiated_by_user_id == user.id)) or 0
            incoming = db.scalar(select(func.count(Offer.id)).where(Offer.recipient_user_id == user.id, Offer.status == "pending")) or 0
            completed = db.scalar(select(func.count(Handover.id)).join(Offer, Handover.offer_id == Offer.id).where(
                Offer.donation_id.in_(select(Donation.id).where(Donation.donor_id == user.id)),
                Handover.status.in_(["completed", "partially_completed"]))) or 0
            metrics = {"donations_total": donation_count, "donations_active": active_count,
                "items_available": int(available), "items_donated": int(donated),
                "offers_sent": outgoing, "offers_to_review": incoming, "handovers_completed": completed,
                "unread_notifications": unread}
            return JSONResponse({"role": "donor", "metrics": metrics})

        org_id = db.scalar(select(OrganisationMember.organisation_id).where(OrganisationMember.user_id == user.id))
        if not org_id: return _json_error("No institution is linked to this account.", 409)
        org = db.get(Organisation, org_id)
        req_count = db.scalar(select(func.count(Requirement.id)).where(Requirement.organisation_id == org_id)) or 0
        open_count = db.scalar(select(func.count(Requirement.id)).where(
            Requirement.organisation_id == org_id, Requirement.status.in_(["open", "partially_fulfilled"]))) or 0
        remaining = db.scalar(select(func.coalesce(func.sum(
            Requirement.quantity_requested - Requirement.quantity_reserved - Requirement.quantity_fulfilled), 0)).where(
            Requirement.organisation_id == org_id)) or 0
        received = db.scalar(select(func.coalesce(func.sum(Requirement.quantity_fulfilled), 0)).where(
            Requirement.organisation_id == org_id)) or 0
        pending = db.scalar(select(func.count(Offer.id)).join(Requirement, Offer.requirement_id == Requirement.id).where(
            Requirement.organisation_id == org_id, Offer.recipient_user_id == user.id, Offer.status == "pending")) or 0
        invites = db.scalar(select(func.count(Offer.id)).join(Requirement, Offer.requirement_id == Requirement.id).where(
            Requirement.organisation_id == org_id, Offer.initiated_by_user_id == user.id)) or 0
        completed = db.scalar(select(func.count(Handover.id)).join(Offer, Handover.offer_id == Offer.id).join(
            Requirement, Offer.requirement_id == Requirement.id).where(
            Requirement.organisation_id == org_id, Handover.status.in_(["completed", "partially_completed"]))) or 0
        return JSONResponse({"role": "org_member", "organisation": {
            "id": str(org.id), "name": org.name, "verification_status": org.verification_status,
            "area": org.public_area}, "metrics": {
            "requirements_total": req_count, "requirements_open": open_count,
            "items_still_needed": int(remaining), "items_received": int(received),
            "offers_to_review": pending, "invitations_sent": invites,
            "handovers_completed": completed, "unread_notifications": unread}})
    finally:
        db.close()

async def inbox(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50)).all()
        return JSONResponse([{"id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body,
            "target_type": n.target_type, "target_id": n.target_id, "read": n.read_at is not None,
            "created_at": n.created_at.isoformat()} for n in rows])
    finally: db.close()


async def mark_notification_read(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        try: notification_id = UUID(request.path_params["notification_id"])
        except (ValueError, TypeError): return _json_error("Notification not found.", 404)
        row = db.scalar(select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id))
        if not row: return _json_error("Notification not found.", 404)
        if row.read_at is None:
            row.read_at = datetime.now(timezone.utc)
            db.commit()
        return JSONResponse({"ok": True, "id": str(row.id), "read": True})
    finally: db.close()


async def mark_all_notifications_read(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        now = datetime.now(timezone.utc)
        rows = db.scalars(select(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None))).all()
        for row in rows: row.read_at = now
        db.commit()
        return JSONResponse({"ok": True, "marked_read": len(rows)})
    finally: db.close()


async def admin_pending_organisations(request):
    db = get_session_factory()()
    try:
        admin, denied = _require(db, request, "admin")
        if denied: return denied
        rows = db.scalars(select(Organisation).where(Organisation.verification_status.in_(["pending", "under_review"])).order_by(Organisation.created_at)).all()
        output = []
        for o in rows:
            docs = db.execute(select(VerificationDocument, StoredFile).join(
                StoredFile, VerificationDocument.stored_file_id == StoredFile.id).where(
                VerificationDocument.organisation_id == o.id).order_by(VerificationDocument.created_at.desc())).all()
            output.append({"id": str(o.id), "name": o.name, "type": o.organisation_type,
                "area": o.public_area, "verification_status": o.verification_status,
                "description": o.description, "contact_phone": o.contact_phone,
                "documents": [{"id": str(doc.id), "file_id": str(file.id),
                    "document_type": doc.document_type, "review_status": doc.review_status,
                    "file_url": f"/api/v2/files/{file.id}"} for doc, file in docs]})
        return JSONResponse(output)
    finally: db.close()


async def admin_review_organisation(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        admin, denied = _require(db, request, "admin")
        if denied: return denied
        try: oid = UUID(request.path_params["organisation_id"])
        except ValueError: return _json_error("Invalid organisation ID.", 422)
        org = db.get(Organisation, oid)
        if not org: return _json_error("Institution not found.", 404)
        action = b.get("action")
        if action not in {"verify", "reject", "suspend", "reopen"}:
            return _json_error("Action must be verify, reject, suspend or reopen.", 422)
        if action == "verify":
            approved = db.scalar(select(VerificationDocument.id).where(
                VerificationDocument.organisation_id == org.id,
                VerificationDocument.review_status == "approved").limit(1))
            if not approved:
                return _json_error("Approve at least one institution verification document before verifying this institution.", 409)
        new_status = {"verify": "verified", "reject": "rejected", "suspend": "suspended", "reopen": "pending"}[action]
        org.verification_status = new_status
        _audit(db, admin, f"organisation.{action}", "organisation", org.id,
               {"note": str(b.get("note") or "").strip()[:1000]})
        owners = db.scalars(select(User).join(OrganisationMember).where(
            OrganisationMember.organisation_id == org.id, OrganisationMember.member_role == "owner")).all()
        for owner in owners:
            _notify(db, owner.id, "organisation_review", "Institution verification updated",
                f"Your institution verification status is now {new_status}.", "organisation", org.id)
        db.commit()
        return JSONResponse({"id": str(org.id), "verification_status": new_status})
    finally: db.close()


async def upload_donation_photo(request):
    from pathlib import Path
    import re
    try: form = await request.form()
    except Exception: return _json_error("Multipart form upload is unavailable. Install python-multipart.", 400)
    upload = form.get("file")
    if not upload or not hasattr(upload, "file"):
        return _json_error("Choose an image file to upload.", 422)
    db = get_session_factory()()
    stored = None
    try:
        user, denied = _require(db, request, "donor")
        if denied: return denied
        try: did = UUID(request.path_params["donation_id"])
        except ValueError: return _json_error("Invalid donation ID.", 422)
        donation = db.get(Donation, did)
        if not donation: return _json_error("Donation not found.", 404)
        if donation.donor_id != user.id: return _json_error("You can only add photos to your own donation.", 403)
        count = db.scalar(select(DonationPhoto.id).where(DonationPhoto.donation_id == did).limit(5))
        if count and len(db.scalars(select(DonationPhoto.id).where(DonationPhoto.donation_id == did)).all()) >= 5:
            return _json_error("A donation can have up to five photos.", 422)
        stored = storage.save_upload(upload.file, "donation-photo", str(user.id))
        original = Path(upload.filename or "photo").name
        original = re.sub(r"[^A-Za-z0-9._ -]", "", original)[:255] or "photo"
        file_row = StoredFile(owner_user_id=user.id, purpose="donation-photo", object_key=stored.key,
            original_name=original, content_type=stored.content_type, size_bytes=stored.size, visibility="public")
        db.add(file_row); db.flush()
        photo = DonationPhoto(donation_id=did, stored_file_id=file_row.id,
            display_order=len(db.scalars(select(DonationPhoto.id).where(DonationPhoto.donation_id == did)).all()))
        db.add(photo); db.flush(); _audit(db, user, "donation.photo_uploaded", "donation", did)
        db.commit()
        return JSONResponse({"id": str(photo.id), "file_id": str(file_row.id),
            "url": f"/api/v2/files/{file_row.id}", "content_type": file_row.content_type,
            "size_bytes": file_row.size_bytes}, status_code=201)
    except storage.StorageError as exc:
        db.rollback(); return _json_error(str(exc), 422)
    except Exception:
        db.rollback()
        if stored:
            try: storage.delete_object(stored.key)
            except Exception: pass
        raise
    finally: db.close()


async def upload_verification_document(request):
    from pathlib import Path
    import re
    try: form = await request.form()
    except Exception: return _json_error("Multipart form upload is unavailable. Install python-multipart.", 400)
    upload = form.get("file")
    doc_type = str(form.get("document_type") or "other")
    if not upload or not hasattr(upload, "file"):
        return _json_error("Choose a verification document to upload.", 422)
    if doc_type not in {"registration_certificate", "trust_deed", "school_recognition", "other"}:
        return _json_error("Invalid verification document type.", 422)
    db = get_session_factory()()
    stored = None
    try:
        user, denied = _require(db, request, "org_member")
        if denied: return denied
        try: oid = UUID(request.path_params["organisation_id"])
        except ValueError: return _json_error("Invalid organisation ID.", 422)
        member = db.scalar(select(OrganisationMember).where(OrganisationMember.organisation_id == oid, OrganisationMember.user_id == user.id))
        org = db.get(Organisation, oid)
        if not org or not member or member.member_role != "owner":
            return _json_error("Only an institution owner can upload its verification documents.", 403)
        stored = storage.save_upload(upload.file, "verification-document", str(user.id))
        original = Path(upload.filename or "document").name
        original = re.sub(r"[^A-Za-z0-9._ -]", "", original)[:255] or "document"
        file_row = StoredFile(owner_user_id=user.id, purpose="verification-document", object_key=stored.key,
            original_name=original, content_type=stored.content_type, size_bytes=stored.size, visibility="private")
        db.add(file_row); db.flush()
        document = VerificationDocument(organisation_id=oid, stored_file_id=file_row.id,
            document_type=doc_type, review_status="pending")
        db.add(document); db.flush()
        org.verification_status = "under_review"
        _audit(db, user, "organisation.document_uploaded", "verification_document", document.id)
        db.commit()
        return JSONResponse({"id": str(document.id), "file_id": str(file_row.id), "review_status": document.review_status,
            "message": "Document uploaded privately for verification."}, status_code=201)
    except storage.StorageError as exc:
        db.rollback(); return _json_error(str(exc), 422)
    except Exception:
        db.rollback()
        if stored:
            try: storage.delete_object(stored.key)
            except Exception: pass
        raise
    finally: db.close()


async def serve_file(request):
    db = get_session_factory()()
    try:
        try: fid = UUID(request.path_params["file_id"])
        except ValueError: return _json_error("Invalid file ID.", 422)
        row = db.get(StoredFile, fid)
        if not row: return _json_error("File not found.", 404)
        if row.visibility == "private":
            user, denied = _require(db, request, "donor", "org_member", "admin")
            if denied: return denied
            if user.role != "admin":
                doc = db.scalar(select(VerificationDocument).where(VerificationDocument.stored_file_id == row.id))
                member = db.scalar(select(OrganisationMember).where(OrganisationMember.organisation_id == doc.organisation_id,
                    OrganisationMember.user_id == user.id)) if doc else None
                if not member: return _json_error("You do not have permission to view this private document.", 403)
        else:
            # Donation photos are public only while attached to a published donation.
            photo = db.scalar(select(DonationPhoto).where(DonationPhoto.stored_file_id == row.id))
            donation = db.get(Donation, photo.donation_id) if photo else None
            if not donation or donation.status in {"withdrawn", "rejected"}:
                return _json_error("File not found.", 404)
        url = storage.signed_url(row.object_key)
        if url: return RedirectResponse(url, status_code=302)
        try: data = storage.read_object(row.object_key)
        except storage.StorageError: return _json_error("File not found.", 404)
        return Response(data, media_type=row.content_type, headers={"Cache-Control": "private, max-age=300" if row.visibility == "private" else "public, max-age=3600"})
    finally: db.close()


async def admin_review_verification_document(request):
    try: b = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        admin, denied = _require(db, request, "admin")
        if denied: return denied
        try: doc_id = UUID(request.path_params["document_id"])
        except ValueError: return _json_error("Invalid document ID.", 422)
        doc = db.get(VerificationDocument, doc_id)
        if not doc: return _json_error("Verification document not found.", 404)
        action = b.get("action")
        if action not in {"approve", "reject"}: return _json_error("Action must be approve or reject.", 422)
        doc.review_status = "approved" if action == "approve" else "rejected"
        doc.reviewer_user_id = admin.id
        doc.review_note = str(b.get("note") or "").strip()[:1000] or None
        doc.reviewed_at = datetime.now(timezone.utc)
        _audit(db, admin, f"verification_document.{action}", "verification_document", doc.id)
        db.commit()
        return JSONResponse({"id": str(doc.id), "review_status": doc.review_status})
    finally: db.close()



async def schedule_handover(request):
    try:
        b = await _body(request)
    except Exception:
        return _json_error("Invalid JSON body.", 400)
    raw = str(b.get("scheduled_at") or "").strip()
    try:
        scheduled = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if scheduled.tzinfo is None:
            return _json_error("Send the scheduled time with a timezone.", 422)
        scheduled = scheduled.astimezone(timezone.utc)
    except ValueError:
        return _json_error("Provide a valid ISO 8601 scheduled time.", 422)
    now = datetime.now(timezone.utc)
    if scheduled <= now or scheduled > now + timedelta(days=90):
        return _json_error("Choose a handover time within the next 90 days.", 422)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        try: hid = UUID(request.path_params["handover_id"])
        except ValueError: return _json_error("Invalid handover ID.", 422)
        row = db.execute(select(Handover, Offer).join(Offer, Handover.offer_id == Offer.id).where(
            Handover.id == hid, or_(Offer.initiated_by_user_id == user.id, Offer.recipient_user_id == user.id))).first()
        if not row: return _json_error("Handover not found.", 404)
        handover, offer = row
        if handover.status not in {"proposed", "scheduled"}:
            return _json_error("Only proposed handovers can be scheduled or rescheduled.", 409)
        handover.scheduled_at = scheduled
        handover.status = "scheduled"
        _audit(db, user, "handover.scheduled", "handover", handover.id,
               {"scheduled_at": scheduled.isoformat()})
        other_user_id = offer.recipient_user_id if user.id == offer.initiated_by_user_id else offer.initiated_by_user_id
        _notify(db, other_user_id, "handover_scheduled", "Handover time proposed",
            f"A handover has been scheduled for {scheduled.isoformat()}.", "handover", handover.id)
        db.commit()
        return JSONResponse({"id": str(handover.id), "status": handover.status,
            "scheduled_at": scheduled.isoformat()})
    finally:
        db.close()

async def cancel_handover(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        try: hid = UUID(request.path_params["handover_id"])
        except ValueError: return _json_error("Invalid handover ID.", 422)
        h = db.scalar(select(Handover).where(Handover.id == hid).with_for_update())
        if not h: return _json_error("Handover not found.", 404)
        offer = db.get(Offer, h.offer_id)
        d = db.scalar(select(Donation).where(Donation.id == offer.donation_id).with_for_update())
        r = db.scalar(select(Requirement).where(Requirement.id == offer.requirement_id).with_for_update())
        is_donor = user.id == d.donor_id
        is_org_member = db.scalar(select(OrganisationMember.organisation_id).where(
            OrganisationMember.organisation_id == r.organisation_id,
            OrganisationMember.user_id == user.id)) is not None
        if not (is_donor or is_org_member): return _json_error("You are not a participant in this handover.", 403)
        if h.status not in {"proposed", "scheduled", "in_progress"}:
            return _json_error("This handover can no longer be cancelled.", 409)
        has_confirmation = db.scalar(select(HandoverConfirmation.id).where(HandoverConfirmation.handover_id == h.id).limit(1))
        if has_confirmation:
            return _json_error("A handover with a submitted confirmation must be resolved, not cancelled.", 409)
        d.quantity_reserved -= h.quantity_agreed
        r.quantity_reserved -= h.quantity_agreed
        d.status = "active" if d.quantity_donated + d.quantity_reserved < d.quantity_total else "fully_reserved"
        r.status = "open" if r.quantity_fulfilled + r.quantity_reserved == 0 else "partially_fulfilled"
        h.status = "cancelled"
        offer.status = "cancelled"
        _audit(db, user, "handover.cancelled", "handover", h.id)
        other_user_id = offer.recipient_user_id if user.id == offer.initiated_by_user_id else offer.initiated_by_user_id
        _notify(db, other_user_id, "handover_cancelled", "Handover cancelled", "The proposed donation handover was cancelled and its reserved quantity has been released.", "handover", h.id)
        db.commit()
        return JSONResponse({"id": str(h.id), "status": h.status, "released_quantity": h.quantity_agreed})
    finally: db.close()


async def list_offers(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        stmt = select(Offer, Donation, Requirement, Organisation, Handover).join(
            Donation, Offer.donation_id == Donation.id).join(
            Requirement, Offer.requirement_id == Requirement.id).join(
            Organisation, Requirement.organisation_id == Organisation.id).outerjoin(
            Handover, Handover.offer_id == Offer.id).where(
            or_(Offer.initiated_by_user_id == user.id, Offer.recipient_user_id == user.id))
        rows = db.execute(stmt.order_by(Offer.created_at.desc()).limit(100)).all()
        output = []
        for offer, donation, requirement, org, handover in rows:
            confirmations = db.scalars(select(HandoverConfirmation).where(
                HandoverConfirmation.handover_id == handover.id)).all() if handover else []
            output.append({"id": str(offer.id), "donation_id": str(donation.id),
                "requirement_id": str(requirement.id), "donation_title": donation.title,
                "requirement_title": requirement.title, "organisation": org.name,
                "quantity": offer.quantity, "status": offer.status,
                "incoming": offer.recipient_user_id == user.id,
                "created_at": offer.created_at.isoformat(),
                "handover": ({"id": str(handover.id), "status": handover.status,
                    "quantity_agreed": handover.quantity_agreed,
                    "quantity_received": handover.quantity_received,
                    "scheduled_at": handover.scheduled_at.isoformat() if handover.scheduled_at else None,
                    "confirmed_by_me": any(c.confirmed_by_user_id == user.id for c in confirmations),
                    "confirmation_count": len(confirmations)} if handover else None)})
        return JSONResponse(output)
    finally: db.close()

# Owner listing management ---------------------------------------------------
def _listing_has_live_offer(db, kind, listing_id):
    column = Offer.donation_id if kind == "donation" else Offer.requirement_id
    return db.scalar(select(Offer.id).where(column == listing_id,
        Offer.status.in_(["pending", "accepted"])).limit(1)) is not None


def _listing_access(db, user, kind, listing):
    if kind == "donation":
        return user.role == "donor" and listing.donor_id == user.id
    if user.role != "org_member":
        return False
    return db.scalar(select(OrganisationMember.user_id).where(
        OrganisationMember.organisation_id == listing.organisation_id,
        OrganisationMember.user_id == user.id)) is not None


async def my_listings(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        output = []
        if user.role == "donor":
            rows = db.execute(select(Donation, Category).join(Category)
                .where(Donation.donor_id == user.id).order_by(Donation.created_at.desc())).all()
            for item, category in rows:
                output.append({"kind": "donation", "id": str(item.id), "title": item.title,
                    "description": item.description, "category": category.label, "area": item.area,
                    "quantity_total": item.quantity_total, "quantity_reserved": item.quantity_reserved,
                    "quantity_completed": item.quantity_donated,
                    "quantity_remaining": item.quantity_total-item.quantity_reserved-item.quantity_donated,
                    "condition": item.condition, "status": item.status,
                    "created_at": item.created_at.isoformat()})
        else:
            org = db.scalar(select(Organisation).join(OrganisationMember)
                .where(OrganisationMember.user_id == user.id))
            if org:
                rows = db.execute(select(Requirement, Category).join(Category)
                    .where(Requirement.organisation_id == org.id)
                    .order_by(Requirement.created_at.desc())).all()
                for item, category in rows:
                    output.append({"kind": "requirement", "id": str(item.id), "title": item.title,
                        "description": item.description, "category": category.label, "area": item.area,
                        "quantity_total": item.quantity_requested, "quantity_reserved": item.quantity_reserved,
                        "quantity_completed": item.quantity_fulfilled,
                        "quantity_remaining": item.quantity_requested-item.quantity_reserved-item.quantity_fulfilled,
                        "status": item.status, "created_at": item.created_at.isoformat()})
        return JSONResponse(output)
    finally:
        db.close()


async def update_listing(request):
    kind = request.path_params["kind"]
    try: listing_id = UUID(request.path_params["listing_id"])
    except (ValueError, TypeError): listing_id = None
    if kind not in {"donation", "requirement"} or not listing_id:
        return _json_error("Listing not found.", 404)
    try: body = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        model = Donation if kind == "donation" else Requirement
        item = db.get(model, listing_id)
        if not item or not _listing_access(db, user, kind, item):
            return _json_error("Listing not found.", 404)
        if _listing_has_live_offer(db, kind, item.id):
            return _json_error("This listing has a pending or accepted offer. Finish or withdraw that offer before editing listing details.", 409)
        title = str(body.get("title", item.title)).strip()
        description = str(body.get("description", item.description or "")).strip() or None
        area = canonical_area(body.get("area", item.area))
        if not title or len(title) > 120 or not area:
            return _json_error("Provide a title (up to 120 characters) and a valid area.", 422)
        quantity_key = "quantity_total" if kind == "donation" else "quantity_requested"
        try: quantity = int(body.get(quantity_key, getattr(item, quantity_key)))
        except (TypeError, ValueError): quantity = 0
        committed = item.quantity_reserved + (item.quantity_donated if kind == "donation" else item.quantity_fulfilled)
        if quantity < 1 or quantity < committed:
            return _json_error(f"Quantity cannot be less than the {committed} item(s) already reserved or completed.", 422)
        item.title, item.description, item.area = title, description, area
        setattr(item, quantity_key, quantity)
        if kind == "donation" and item.status == "fully_reserved" and quantity > committed:
            item.status = "active"
        db.flush()
        _audit(db, user, f"{kind}.updated", kind, item.id,
            {"title": title, "area": area, "quantity": quantity})
        db.commit()
        return JSONResponse({"ok": True, "id": str(item.id), "title": item.title,
            "status": item.status, "quantity_total": quantity})
    except IntegrityError:
        db.rollback()
        return _json_error("The listing could not be updated because it conflicts with existing activity.", 409)
    finally:
        db.close()


async def change_listing_status(request):
    kind = request.path_params["kind"]
    try: listing_id = UUID(request.path_params["listing_id"])
    except (ValueError, TypeError): listing_id = None
    if kind not in {"donation", "requirement"} or not listing_id:
        return _json_error("Listing not found.", 404)
    try: body = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    action = str(body.get("action") or "").lower()
    if action not in {"pause", "resume", "withdraw", "close"}:
        return _json_error("Choose pause, resume, withdraw or close.", 422)
    if kind == "donation" and action == "close": return _json_error("Use withdraw for donations.", 422)
    if kind == "requirement" and action == "withdraw": return _json_error("Use close for requirements.", 422)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        model = Donation if kind == "donation" else Requirement
        item = db.get(model, listing_id)
        if not item or not _listing_access(db, user, kind, item):
            return _json_error("Listing not found.", 404)
        active_offer = _listing_has_live_offer(db, kind, item.id)
        if action in {"pause", "withdraw", "close"} and active_offer:
            return _json_error("This listing has a pending or accepted offer. Resolve it before changing the listing status.", 409)
        reserved = item.quantity_reserved
        if action in {"withdraw", "close"} and reserved:
            return _json_error("This listing has reserved items. Complete or cancel the handover before closing it.", 409)
        if action == "pause":
            if item.status not in ({"active", "partially_fulfilled"} if kind == "donation" else {"open", "partially_fulfilled"}):
                return _json_error("Only an active listing can be paused.", 409)
            item.status = "paused"
        elif action == "resume":
            if item.status != "paused": return _json_error("Only a paused listing can be resumed.", 409)
            remaining = (item.quantity_total-item.quantity_reserved-item.quantity_donated) if kind == "donation" else (item.quantity_requested-item.quantity_reserved-item.quantity_fulfilled)
            if remaining <= 0: return _json_error("There is no remaining quantity to make available.", 409)
            completed = item.quantity_donated if kind == "donation" else item.quantity_fulfilled
            item.status = ("partially_fulfilled" if completed else ("active" if kind == "donation" else "open"))
        elif action in {"withdraw", "close"}:
            if item.status in {"withdrawn", "closed", "completed", "rejected"}:
                return _json_error("This listing is already closed.", 409)
            item.status = "withdrawn" if kind == "donation" else "closed"
        db.flush()
        audit_action = {"pause": "paused", "resume": "resumed", "withdraw": "withdrawn", "close": "closed"}[action]
        _audit(db, user, f"{kind}.{audit_action}", kind, item.id)
        db.commit()
        return JSONResponse({"ok": True, "id": str(item.id), "status": item.status})
    finally:
        db.close()


# Trust & safety: community reports and private listing history ----------------
async def create_report(request):
    try: body = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    target_type = str(body.get("target_type") or "").lower()
    target_id = str(body.get("target_id") or "")
    reason = str(body.get("reason") or "").lower()
    details = str(body.get("details") or "").strip() or None
    if target_type not in {"donation", "requirement", "organisation"} or reason not in {"misleading", "inappropriate", "duplicate", "safety_concern", "suspicious", "other"}:
        return _json_error("Choose a valid item to report and a report reason.", 422)
    if details and len(details) > 1000: return _json_error("Details must be 1,000 characters or fewer.", 422)
    try: target_uuid = UUID(target_id)
    except (ValueError, TypeError): return _json_error("The reported item could not be found.", 404)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        owner_id = None
        if target_type == "donation":
            target = db.get(Donation, target_uuid)
            if target: owner_id = target.donor_id
        elif target_type == "requirement":
            target = db.get(Requirement, target_uuid)
            if target:
                owner_id = target.created_by_user_id
        else:
            target = db.get(Organisation, target_uuid)
            if target:
                member_ids = db.scalars(select(OrganisationMember.user_id).where(OrganisationMember.organisation_id == target.id)).all()
                owner_id = user.id if user.id in member_ids else None
        if not target: return _json_error("The reported item could not be found.", 404)
        if target_type == "donation" and owner_id == user.id: return _json_error("You cannot report your own listing.", 403)
        if target_type == "requirement" and db.scalar(select(OrganisationMember.user_id).where(OrganisationMember.organisation_id == target.organisation_id, OrganisationMember.user_id == user.id)):
            return _json_error("You cannot report your own institution's requirement.", 403)
        if target_type == "organisation" and owner_id == user.id: return _json_error("You cannot report your own institution.", 403)
        duplicate = db.scalar(select(Report.id).where(Report.reporter_user_id == user.id, Report.target_type == target_type, Report.target_id == target_id, Report.status.in_(["open", "in_review"])))
        if duplicate: return _json_error("You already have an open report for this item.", 409)
        report = Report(reporter_user_id=user.id, target_type=target_type, target_id=target_id, reason=reason, details=details, status="open")
        db.add(report); db.flush(); _audit(db, user, "report.created", target_type, target_id, {"report_id": str(report.id), "reason": reason})
        admins = db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))).all()
        for admin in admins: _notify(db, admin.id, "safety_report", "A community report needs review", f"A {target_type} was reported for: {reason.replace('_', ' ')}.", "report", report.id)
        db.commit()
        return JSONResponse({"id": str(report.id), "status": report.status, "message": "Report submitted privately for review."}, status_code=201)
    finally: db.close()


async def admin_reports(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "admin")
        if denied: return denied
        rows = db.scalars(select(Report).order_by(Report.created_at.desc()).limit(200)).all()
        output = []
        for r in rows:
            reporter = db.get(User, r.reporter_user_id)
            target_name = "Unavailable item"
            if r.target_type == "donation":
                target = db.get(Donation, UUID(r.target_id)); target_name = target.title if target else target_name
            elif r.target_type == "requirement":
                target = db.get(Requirement, UUID(r.target_id)); target_name = target.title if target else target_name
            else:
                target = db.get(Organisation, UUID(r.target_id)); target_name = target.name if target else target_name
            output.append({"id": str(r.id), "target_type": r.target_type, "target_id": r.target_id, "target_name": target_name, "reason": r.reason, "details": r.details, "status": r.status, "reporter": reporter.name if reporter else "Former user", "created_at": r.created_at.isoformat(), "reviewer_note": r.reviewer_note})
        return JSONResponse(output)
    finally: db.close()


async def admin_review_report(request):
    try: body = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    action = str(body.get("action") or "").lower(); note = str(body.get("note") or "").strip()
    if action not in {"in_review", "resolve", "dismiss"} or len(note) > 1000: return _json_error("Choose a valid review action and a note up to 1,000 characters.", 422)
    try: report_id = UUID(request.path_params["report_id"])
    except (ValueError, TypeError): return _json_error("Report not found.", 404)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "admin")
        if denied: return denied
        report = db.get(Report, report_id)
        if not report: return _json_error("Report not found.", 404)
        if report.status in {"resolved", "dismissed"}: return _json_error("This report has already been closed.", 409)
        report.status = {"in_review": "in_review", "resolve": "resolved", "dismiss": "dismissed"}[action]
        report.reviewer_user_id = user.id; report.reviewer_note = note or None; report.reviewed_at = datetime.now(timezone.utc)
        _audit(db, user, f"report.{report.status}", "report", report.id, {"target_type": report.target_type, "target_id": report.target_id})
        reporter = db.get(User, report.reporter_user_id)
        if reporter: _notify(db, reporter.id, "report_update", "Your report was reviewed", f"Your report has been marked {report.status.replace('_', ' ')}.", "report", report.id)
        db.commit()
        return JSONResponse({"id": str(report.id), "status": report.status})
    finally: db.close()


async def listing_activity(request):
    kind = request.path_params["kind"]
    try: listing_id = UUID(request.path_params["listing_id"])
    except (ValueError, TypeError): return _json_error("Listing not found.", 404)
    if kind not in {"donation", "requirement"}: return _json_error("Listing not found.", 404)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        model = Donation if kind == "donation" else Requirement
        listing = db.get(model, listing_id)
        if not listing or not _listing_access(db, user, kind, listing): return _json_error("Listing not found.", 404)
        logs = db.scalars(select(AuditLog).where(AuditLog.entity_type == kind, AuditLog.entity_id == str(listing_id)).order_by(AuditLog.created_at.desc()).limit(100)).all()
        import json
        return JSONResponse([{"action": x.action, "details": json.loads(x.details) if x.details else {}, "created_at": x.created_at.isoformat()} for x in logs])
    finally: db.close()

# Profiles, post-acceptance coordination and account administration -----------
async def profile(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        data = {"id": str(user.id), "name": user.name, "email": user.email,
                "phone": user.phone, "role": user.role}
        if user.role == "org_member":
            row = db.execute(select(Organisation, OrganisationMember.member_role)
                .join(OrganisationMember).where(OrganisationMember.user_id == user.id)).first()
            if row:
                org, member_role = row
                data["organisation"] = {"id": str(org.id), "name": org.name,
                    "type": org.organisation_type, "description": org.description,
                    "area": org.public_area, "contact_phone": org.contact_phone,
                    "verification_status": org.verification_status, "member_role": member_role}
        return JSONResponse(data)
    finally: db.close()


async def update_profile(request):
    try: body = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        name = str(body.get("name", user.name)).strip()
        phone = str(body.get("phone", user.phone or "")).strip() or None
        if not 2 <= len(name) <= 100: return _json_error("Name must be 2 to 100 characters.", 422)
        if phone and (len(phone) > 30 or len(phone) < 7): return _json_error("Enter a valid contact number.", 422)
        user.name, user.phone = name, phone
        org = None
        if user.role == "org_member":
            row = db.execute(select(Organisation, OrganisationMember.member_role)
                .join(OrganisationMember).where(OrganisationMember.user_id == user.id)).first()
            if row:
                org, member_role = row
                if member_role not in {"owner", "manager"} and any(k in body for k in ("organisation_name", "description", "area", "contact_phone")):
                    return _json_error("Only an institution owner or manager can edit institution details.", 403)
                if "organisation_name" in body:
                    value = str(body["organisation_name"]).strip()
                    if not 2 <= len(value) <= 160: return _json_error("Institution name must be 2 to 160 characters.", 422)
                    org.name = value
                if "description" in body:
                    value = str(body["description"]).strip()
                    if len(value) > 2000: return _json_error("Description must be 2,000 characters or fewer.", 422)
                    org.description = value or None
                if "area" in body:
                    value = canonical_area(body["area"])
                    if not value: return _json_error("Choose a valid service area.", 422)
                    org.public_area = value
                if "contact_phone" in body:
                    value = str(body["contact_phone"]).strip()
                    if value and not 7 <= len(value) <= 30: return _json_error("Enter a valid institution contact number.", 422)
                    org.contact_phone = value or None
        _audit(db, user, "profile.updated", "user", user.id)
        db.commit()
        return JSONResponse({"ok": True, "name": user.name, "phone": user.phone,
            "organisation": ({"name": org.name, "description": org.description, "area": org.public_area,
                "contact_phone": org.contact_phone, "verification_status": org.verification_status} if org else None)})
    finally: db.close()


async def offer_contacts(request):
    try: offer_id = UUID(request.path_params["offer_id"])
    except (ValueError, TypeError): return _json_error("Offer not found.", 404)
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "donor", "org_member")
        if denied: return denied
        offer = db.get(Offer, offer_id)
        if not offer: return _json_error("Offer not found.", 404)
        donation, requirement = db.get(Donation, offer.donation_id), db.get(Requirement, offer.requirement_id)
        is_donor = donation.donor_id == user.id
        org_member = db.scalar(select(OrganisationMember.user_id).where(
            OrganisationMember.organisation_id == requirement.organisation_id,
            OrganisationMember.user_id == user.id)) is not None
        if not (is_donor or org_member): return _json_error("You are not a participant in this offer.", 403)
        if offer.status != "accepted": return _json_error("Contact details are available after the offer is accepted.", 409)
        org = db.get(Organisation, requirement.organisation_id)
        if is_donor:
            counterpart = db.get(User, offer.recipient_user_id)
            return JSONResponse({"name": counterpart.name if counterpart else org.name,
                "email": counterpart.email if counterpart else None,
                "phone": (org.contact_phone or (counterpart.phone if counterpart else None)),
                "organisation": org.name, "area": org.public_area,
                "note": "Use these details only to coordinate this NeedBridge handover."})
        counterpart = db.get(User, donation.donor_id)
        return JSONResponse({"name": counterpart.name, "email": counterpart.email,
            "phone": counterpart.phone, "organisation": None, "area": donation.area,
            "note": "Use these details only to coordinate this NeedBridge handover."})
    finally: db.close()


async def admin_accounts(request):
    db = get_session_factory()()
    try:
        user, denied = _require(db, request, "admin")
        if denied: return denied
        rows = db.scalars(select(User).where(User.role != "admin").order_by(User.created_at.desc()).limit(300)).all()
        return JSONResponse([{"id": str(x.id), "name": x.name, "email": x.email,
            "role": x.role, "phone": x.phone, "is_active": x.is_active,
            "created_at": x.created_at.isoformat()} for x in rows])
    finally: db.close()


async def admin_set_account_status(request):
    try: body = await _body(request)
    except Exception: return _json_error("Invalid JSON body.", 400)
    try: target_id = UUID(request.path_params["user_id"])
    except (ValueError, TypeError): return _json_error("Account not found.", 404)
    active = body.get("active")
    if not isinstance(active, bool): return _json_error("Provide active as true or false.", 422)
    db = get_session_factory()()
    try:
        admin, denied = _require(db, request, "admin")
        if denied: return denied
        target = db.get(User, target_id)
        if not target or target.role == "admin": return _json_error("Account not found.", 404)
        if target.id == admin.id: return _json_error("You cannot change your own account status.", 403)
        if target.is_active == active: return JSONResponse({"id": str(target.id), "is_active": active})
        target.is_active = active
        if not active and target.role == "org_member":
            org_ids = db.scalars(select(OrganisationMember.organisation_id).where(OrganisationMember.user_id == target.id)).all()
            for org_id in org_ids:
                org = db.get(Organisation, org_id)
                if org: org.verification_status = "suspended"
        _audit(db, admin, "account.activated" if active else "account.suspended", "user", target.id)
        _notify(db, target.id, "account_status", "Account access updated",
            "Your account has been reactivated." if active else "Your account has been suspended. Contact NeedBridge support if you believe this is a mistake.", "user", target.id)
        db.commit()
        return JSONResponse({"id": str(target.id), "is_active": target.is_active})
    finally: db.close()
