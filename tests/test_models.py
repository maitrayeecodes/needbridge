from sqlalchemy import create_engine
from backend.models import Base


def test_initial_schema_creates_all_core_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert {
        "users", "organisations", "organisation_members", "categories",
        "donations", "requirements", "match_suggestions", "offers",
        "handovers", "handover_confirmations", "stored_files",
        "notifications", "audit_logs",
    }.issubset(set(Base.metadata.tables))
