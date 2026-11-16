"""Initial relational data model for NeedBridge's PostgreSQL backend.

Quantities are stored on listings and reservations are updated in the same database
transaction as offer acceptance. File bytes live in object storage; StoredFile keeps
only metadata and an opaque object key.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index,
                        Integer, String, Text, UniqueConstraint, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid


def now_utc():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (CheckConstraint("role IN ('donor','org_member','admin')", name="ck_users_role"),)


class Organisation(Base):
    __tablename__ = "organisations"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    organisation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    public_area: Mapped[str] = mapped_column(String(100), nullable=False)
    private_address: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("organisation_type IN ('school','ngo','community_group','other')", name="ck_org_type"),
        CheckConstraint("verification_status IN ('pending','under_review','verified','rejected','suspended')", name="ck_org_verification"),
    )


class OrganisationMember(Base):
    __tablename__ = "organisation_members"
    organisation_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    member_role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint("member_role IN ('owner','manager','member')", name="ck_org_member_role"),)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Donation(Base):
    __tablename__ = "donations"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    donor_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(String(16), nullable=False)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    quantity_total: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_donated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("condition IN ('new','good','fair')", name="ck_donation_condition"),
        CheckConstraint("quantity_total > 0 AND quantity_reserved >= 0 AND quantity_donated >= 0 AND quantity_reserved + quantity_donated <= quantity_total", name="ck_donation_quantities"),
        CheckConstraint("age_min IS NULL OR age_min BETWEEN 3 AND 18", name="ck_donation_age_min"),
        CheckConstraint("age_max IS NULL OR age_max BETWEEN 3 AND 18", name="ck_donation_age_max"),
        CheckConstraint("age_min IS NULL OR age_max IS NULL OR age_min <= age_max", name="ck_donation_age_range"),
    )


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organisation_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_fulfilled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("quantity_requested > 0 AND quantity_reserved >= 0 AND quantity_fulfilled >= 0 AND quantity_reserved + quantity_fulfilled <= quantity_requested", name="ck_requirement_quantities"),
        CheckConstraint("age_min IS NULL OR age_min BETWEEN 3 AND 18", name="ck_requirement_age_min"),
        CheckConstraint("age_max IS NULL OR age_max BETWEEN 3 AND 18", name="ck_requirement_age_max"),
        CheckConstraint("age_min IS NULL OR age_max IS NULL OR age_min <= age_max", name="ck_requirement_age_range"),
    )


class MatchSuggestion(Base):
    __tablename__ = "match_suggestions"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    donation_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("donations.id", ondelete="CASCADE"), nullable=False)
    requirement_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(30), nullable=False, default="rules-v1")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint("donation_id", "requirement_id", name="uq_match_pair"), CheckConstraint("score BETWEEN 0 AND 100", name="ck_match_score"))


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    donation_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("donations.id", ondelete="RESTRICT"), nullable=False, index=True)
    requirement_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id", ondelete="RESTRICT"), nullable=False, index=True)
    initiated_by_user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recipient_user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_offer_quantity"),
        CheckConstraint("status IN ('pending','accepted','declined','withdrawn','cancelled','expired','completed')", name="ck_offer_status"),
        Index("ix_offer_active_pair", "donation_id", "requirement_id", unique=True, postgresql_where=text("status IN ('pending','accepted')"), sqlite_where=text("status IN ('pending','accepted')")),
    )


class Handover(Base):
    __tablename__ = "handovers"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    offer_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, unique=True)
    quantity_agreed: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("quantity_agreed > 0 AND (quantity_received IS NULL OR (quantity_received >= 0 AND quantity_received <= quantity_agreed))", name="ck_handover_quantities"),
        CheckConstraint("status IN ('proposed','scheduled','in_progress','awaiting_confirmation','completed','partially_completed','cancelled','disputed')", name="ck_handover_status"),
    )


class HandoverConfirmation(Base):
    __tablename__ = "handover_confirmations"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    handover_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("handovers.id", ondelete="CASCADE"), nullable=False)
    confirmed_by_user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    party: Mapped[str] = mapped_column(String(12), nullable=False)
    quantity_confirmed: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint("handover_id", "party", name="uq_handover_party_confirmation"), CheckConstraint("party IN ('donor','recipient')", name="ck_confirmation_party"), CheckConstraint("quantity_confirmed >= 0", name="ck_confirmation_quantity"))


class StoredFile(Base):
    __tablename__ = "stored_files"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint("purpose IN ('donation-photo','verification-document')", name="ck_file_purpose"), CheckConstraint("visibility IN ('public','private')", name="ck_file_visibility"), CheckConstraint("size_bytes > 0", name="ck_file_size"))


class DonationPhoto(Base):
    __tablename__ = "donation_photos"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    donation_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("donations.id", ondelete="CASCADE"), nullable=False, index=True)
    stored_file_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False, unique=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint("display_order >= 0", name="ck_donation_photo_order"),)


class VerificationDocument(Base):
    __tablename__ = "verification_documents"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organisation_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    stored_file_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False, unique=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewer_user_id: Mapped[object | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("document_type IN ('registration_certificate','trust_deed','school_recognition','other')", name="ck_verification_document_type"),
        CheckConstraint("review_status IN ('pending','approved','rejected')", name="ck_verification_document_status"),
    )


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(36))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[object | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False, index=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    reporter_user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    reviewer_user_id: Mapped[object | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("target_type IN ('donation','requirement','organisation')", name="ck_report_target_type"),
        CheckConstraint("reason IN ('misleading','inappropriate','duplicate','safety_concern','suspicious','other')", name="ck_report_reason"),
        CheckConstraint("status IN ('open','in_review','resolved','dismissed')", name="ck_report_status"),
    )
