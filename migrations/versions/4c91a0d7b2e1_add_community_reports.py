"""add community reports for trust and safety

Revision ID: 4c91a0d7b2e1
Revises: 2f243868ef18
Create Date: 2026-11-16
"""
from alembic import op
import sqlalchemy as sa

revision = "4c91a0d7b2e1"
down_revision = "2f243868ef18"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=24), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target_type IN ('donation','requirement','organisation')", name="ck_report_target_type"),
        sa.CheckConstraint("reason IN ('misleading','inappropriate','duplicate','safety_concern','suspicious','other')", name="ck_report_reason"),
        sa.CheckConstraint("status IN ('open','in_review','resolved','dismissed')", name="ck_report_status"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_reporter_user_id", "reports", ["reporter_user_id"])
    op.create_index("ix_reports_target_id", "reports", ["target_id"])
    op.create_index("ix_reports_status", "reports", ["status"])

def downgrade():
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_target_id", table_name="reports")
    op.drop_index("ix_reports_reporter_user_id", table_name="reports")
    op.drop_table("reports")
