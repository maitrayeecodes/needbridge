"""Accounts and permissions.

Uses only Python's standard library, plus Starlette's session cookie (which relies on
itsdangerous, already in your requirements.txt). Passwords are never stored: only a salted hash.
"""
import hashlib
import hmac
import os
import re
import sqlite3
from contextlib import closing

from starlette.responses import JSONResponse

from backend import matching
from backend.geo import canonical_area

ROLES = {"donor", "org"}  # admin accounts are made from the command line, never through sign-up
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ITERATIONS = 600_000


def db():
    c = sqlite3.connect(matching.DATA_DIR / "needbridge.db")
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL, area TEXT, pw TEXT NOT NULL)""")
    return c


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    salt, digest = stored.split("$")
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return hmac.compare_digest(test.hex(), digest)


def create_user(name, email, password, role, area=None, allow_admin=False):
    """Returns (user_row, errors). Validates everything before touching the database."""
    errors = []
    name, email = str(name or "").strip(), str(email or "").strip().lower()
    if not 2 <= len(name) <= 60:
        errors.append("Name must be 2 to 60 characters.")
    if not EMAIL.match(email):
        errors.append("Enter a valid email address.")
    if len(str(password or "")) < 8:
        errors.append("Password must be at least 8 characters.")
    if role not in ROLES and not (allow_admin and role == "admin"):
        errors.append("Choose donor or school/NGO.")
    area = canonical_area(area) if area else None
    if errors:
        return None, errors
    with closing(db()) as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            return None, ["An account with this email already exists."]
        cur = c.execute("INSERT INTO users(name,email,role,area,pw) VALUES(?,?,?,?,?)",
                        (name, email, role, area, hash_password(password)))
        c.commit()
        return c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone(), []


def check_login(email, password):
    with closing(db()) as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (str(email or "").strip().lower(),)).fetchone()
    if u is None:  # do the same work anyway so timing does not reveal which emails exist
        verify_password(password or "", hash_password("dummy-password"))
        return None
    return u if verify_password(password or "", u["pw"]) else None


def get_user(uid):
    with closing(db()) as c:
        return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def public(u):
    return {"id": u["id"], "name": u["name"], "role": u["role"], "area": u["area"]}


def current_user(request):
    uid = request.session.get("uid")
    return get_user(uid) if uid else None


def require(request, *roles):
    """Returns (user, None) if allowed, otherwise (None, an error response to send back)."""
    u = current_user(request)
    if u is None:
        return None, JSONResponse({"errors": ["Please log in first."]}, status_code=401)
    if roles and u["role"] not in roles:
        who = " or ".join({"donor": "donor", "org": "school/NGO", "admin": "admin"}[r] for r in roles)
        return None, JSONResponse({"errors": [f"Only {who} accounts can do this."]}, status_code=403)
    return u, None


# ---------- routes ----------
async def _body(request):
    try:
        return await request.json()
    except ValueError:
        return {}


async def signup(request):
    b = await _body(request)
    user, errors = create_user(b.get("name"), b.get("email"), b.get("password"), b.get("role"), b.get("area"))
    if errors:
        return JSONResponse({"errors": errors}, status_code=409 if "exists" in errors[0] else 422)
    request.session["uid"] = user["id"]
    return JSONResponse(public(user), status_code=201)


async def login(request):
    b = await _body(request)
    user = check_login(b.get("email"), b.get("password"))
    if user is None:
        return JSONResponse({"errors": ["Wrong email or password."]}, status_code=401)
    request.session["uid"] = user["id"]
    return JSONResponse(public(user))


async def logout(request):
    request.session.clear()
    return JSONResponse({"ok": True})


async def me(request):
    u = current_user(request)
    return JSONResponse(public(u) if u else None)