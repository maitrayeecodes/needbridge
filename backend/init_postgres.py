"""Seed reference categories and optionally create the first PostgreSQL admin.

Run after `alembic upgrade head` with DATABASE_URL configured.
"""
import os
from sqlalchemy import select
from backend.database import get_session_factory
from backend.models import Category, User
from backend.auth import hash_password

CATEGORIES = [
    ("notebooks", "Notebooks"),
    ("school_bag", "School Bags"),
    ("textbooks", "Textbooks"),
    ("geometry_box", "Geometry Boxes"),
    ("storybooks", "Storybooks"),
    ("stationery", "Stationery"),
    ("clothing", "Clothing"),
    ("footwear", "Footwear"),
    ("toys", "Toys"),
    ("school_supplies", "Other School Supplies"),
]


def main():
    db = get_session_factory()()
    try:
        for slug, label in CATEGORIES:
            if not db.scalar(select(Category.id).where(Category.slug == slug)):
                db.add(Category(slug=slug, label=label, is_active=True))
        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if email and password and not db.scalar(select(User.id).where(User.email == email)):
            db.add(User(name=os.getenv("ADMIN_NAME", "NeedBridge Admin"), email=email,
                password_hash=hash_password(password), role="admin", is_active=True))
        db.commit()
        print("NeedBridge reference data seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
