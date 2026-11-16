import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from uuid import UUID
from starlette.testclient import TestClient

from backend import database
from backend.api import app
from backend.models import Base, Category, User, Donation, Requirement
from backend import storage
from backend.auth import hash_password


@pytest.fixture
def clients(tmp_path, monkeypatch):
    db_file = tmp_path / "needbridge-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    database.get_engine.cache_clear()
    monkeypatch.setattr(storage, "LOCAL_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(storage, "_provider", storage.LocalStorage())
    engine = database.get_engine()
    Base.metadata.create_all(engine)
    factory = database.get_session_factory()
    with factory() as db:
        db.add(Category(id=1, slug="notebooks", label="Notebooks", is_active=True))
        db.add(User(name="Test Admin", email="admin@test.local", password_hash=hash_password("admin-password"), role="admin", is_active=True))
        db.commit()
    yield TestClient(app), TestClient(app), TestClient(app)
    database.get_engine.cache_clear()


def test_end_to_end_offer_reservation_and_dual_confirmation(clients):
    donor, institution, admin = clients
    org_signup = institution.post("/api/v2/auth/signup", json={
        "name": "Institution Owner", "email": "school@test.local", "password": "school-password",
        "role": "org_member", "organisation_name": "Test School", "organisation_type": "school", "area": "Cidco"
    })
    assert org_signup.status_code == 201
    assert org_signup.status_code == 201
    org_me = institution.get("/api/v2/auth/me").json()
    org_id = org_me["organisation"]["id"]
    document = institution.post(f"/api/v2/organisations/{org_id}/verification-documents",
        data={"document_type": "registration_certificate"},
        files={"file": ("certificate.pdf", b"%PDF-1.4\nNeedBridge verification", "application/pdf")})
    assert document.status_code == 201

    admin.post("/api/v2/auth/login", json={"email": "admin@test.local", "password": "admin-password"})
    assert admin.get("/api/v2/files/" + document.json()["file_id"]).status_code == 200
    assert admin.post(f"/api/v2/admin/verification-documents/{document.json()['id']}",
        json={"action": "approve", "note": "Document checked"}).json()["review_status"] == "approved"
    assert admin.post(f"/api/v2/admin/organisations/{org_id}", json={"action": "verify"}).json()["verification_status"] == "verified"

    assert donor.post("/api/v2/auth/signup", json={
        "name": "Helpful Donor", "email": "donor@test.local", "password": "donor-password", "role": "donor"
    }).status_code == 201
    # The donor must not be able to retrieve an institution's private verification document.
    assert donor.get("/api/v2/files/" + document.json()["file_id"]).status_code == 403
    donation = donor.post("/api/v2/donations", json={
        "category_id": 1, "title": "Good notebooks", "condition": "good", "area": "Cidco", "quantity_total": 10
    })
    assert donation.status_code == 201
    photo = donor.post(f"/api/v2/donations/{donation.json()['id']}/photos",
        files={"file": ("notebooks.png", b"\x89PNG\r\n\x1a\nNeedBridge test photo", "image/png")})
    assert photo.status_code == 201
    assert donor.get(photo.json()["url"]).status_code == 200
    requirement = institution.post("/api/v2/requirements", json={
        "category_id": 1, "title": "Notebooks for students", "area": "Cidco", "quantity_requested": 8
    })
    assert requirement.status_code == 201
    public_needs = donor.get("/api/v2/requirements?near_area=Cidco").json()
    assert public_needs[0]["item"] == "Notebooks for students"
    assert public_needs[0]["category"] == "notebooks"
    assert public_needs[0]["distance_km"] == 0.0

    matches = donor.get("/api/v2/matches")
    assert matches.status_code == 200 and matches.json()[0]["score"] >= 50
    offer = donor.post("/api/v2/offers", json={
        "donation_id": donation.json()["id"], "requirement_id": requirement.json()["id"], "quantity": 6
    })
    assert offer.status_code == 201
    assert donor.get("/api/v2/offers").json()[0]["incoming"] is False
    assert institution.get("/api/v2/offers").json()[0]["incoming"] is True
    accepted = institution.post(f"/api/v2/offers/{offer.json()['id']}/respond", json={"action": "accept"})
    assert accepted.status_code == 200
    handover_id = accepted.json()["handover_id"]
    proposed_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    scheduled = donor.post(f"/api/v2/handovers/{handover_id}/schedule", json={"scheduled_at": proposed_time})
    assert scheduled.status_code == 200 and scheduled.json()["status"] == "scheduled"
    assert institution.get("/api/v2/offers").json()[0]["handover"]["scheduled_at"] is not None

    first = donor.post(f"/api/v2/handovers/{handover_id}/confirm", json={"quantity_received": 5})
    assert first.status_code == 200 and first.json()["status"] == "awaiting_confirmation"
    second = institution.post(f"/api/v2/handovers/{handover_id}/confirm", json={"quantity_received": 5})
    assert second.status_code == 200 and second.json()["status"] == "partially_completed"

    with database.get_session_factory()() as db:
        d = db.get(Donation, UUID(donation.json()["id"]))
        r = db.get(Requirement, UUID(requirement.json()["id"]))
        assert (d.quantity_reserved, d.quantity_donated) == (0, 5)
        assert (r.quantity_reserved, r.quantity_fulfilled) == (0, 5)

    # The same matching system also supports an institution-initiated invitation.
    invitation = institution.post("/api/v2/offers", json={
        "donation_id": donation.json()["id"], "requirement_id": requirement.json()["id"], "quantity": 1
    })
    assert invitation.status_code == 201
    accepted_by_donor = donor.post(f"/api/v2/offers/{invitation.json()['id']}/respond", json={"action": "accept"})
    assert accepted_by_donor.status_code == 200
    reverse_handover = accepted_by_donor.json()["handover_id"]
    assert donor.post(f"/api/v2/handovers/{reverse_handover}/confirm", json={"quantity_received": 1}).json()["status"] == "awaiting_confirmation"
    assert institution.post(f"/api/v2/handovers/{reverse_handover}/confirm", json={"quantity_received": 1}).json()["status"] == "completed"
    with database.get_session_factory()() as db:
        d = db.get(Donation, UUID(donation.json()["id"]))
        r = db.get(Requirement, UUID(requirement.json()["id"]))
        assert (d.quantity_reserved, d.quantity_donated) == (0, 6)
        assert (r.quantity_reserved, r.quantity_fulfilled) == (0, 6)

    cancellable = institution.post("/api/v2/offers", json={
        "donation_id": donation.json()["id"], "requirement_id": requirement.json()["id"], "quantity": 2
    })
    assert cancellable.status_code == 201
    accepted_cancel = donor.post(f"/api/v2/offers/{cancellable.json()['id']}/respond", json={"action": "accept"})
    assert accepted_cancel.status_code == 200
    cancel_id = accepted_cancel.json()["handover_id"]
    cancelled = institution.post(f"/api/v2/handovers/{cancel_id}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["released_quantity"] == 2
    with database.get_session_factory()() as db:
        d = db.get(Donation, UUID(donation.json()["id"]))
        r = db.get(Requirement, UUID(requirement.json()["id"]))
        assert (d.quantity_reserved, d.quantity_donated) == (0, 6)
        assert (r.quantity_reserved, r.quantity_fulfilled) == (0, 6)


def test_role_scoped_dashboard_metrics(clients):
    donor, institution, admin = clients
    assert donor.post("/api/v2/auth/signup", json={
        "name": "Dashboard Donor", "email": "dashboard-donor@test.local",
        "password": "donor-password", "role": "donor"
    }).status_code == 201
    created = donor.post("/api/v2/donations", json={
        "category_id": 1, "title": "Reusable notebooks", "condition": "good",
        "area": "Cidco", "quantity_total": 12
    })
    assert created.status_code == 201
    stats = donor.get("/api/v2/dashboard")
    assert stats.status_code == 200
    assert stats.json()["role"] == "donor"
    assert stats.json()["metrics"]["donations_total"] == 1
    assert stats.json()["metrics"]["donations_active"] == 1
    assert stats.json()["metrics"]["items_available"] == 12

    assert institution.post("/api/v2/auth/signup", json={
        "name": "School Owner", "email": "dashboard-school@test.local",
        "password": "school-password", "role": "org_member",
        "organisation_name": "Dashboard School", "organisation_type": "school", "area": "Cidco"
    }).status_code == 201
    org_stats = institution.get("/api/v2/dashboard")
    assert org_stats.status_code == 200
    assert org_stats.json()["role"] == "org_member"
    assert org_stats.json()["metrics"]["requirements_total"] == 0
    assert org_stats.json()["organisation"]["verification_status"] == "pending"

    admin.post("/api/v2/auth/login", json={"email": "admin@test.local", "password": "admin-password"})
    admin_stats = admin.get("/api/v2/dashboard")
    assert admin_stats.status_code == 200
    assert admin_stats.json()["role"] == "admin"
    assert admin_stats.json()["metrics"]["pending_organisations"] == 1


def test_notification_read_state_is_private_and_mark_all_works(clients):
    from backend.models import Notification
    donor, institution, admin = clients
    assert donor.post("/api/v2/auth/signup", json={
        "name": "Notice Donor", "email": "notice-donor@test.local",
        "password": "donor-password", "role": "donor"
    }).status_code == 201
    donor_id = donor.get("/api/v2/auth/me").json()["id"]
    with database.get_session_factory()() as db:
        db.add_all([
            Notification(user_id=UUID(donor_id), kind="offer_received", title="Offer update", body="A school sent an offer."),
            Notification(user_id=UUID(donor_id), kind="handover_scheduled", title="Handover update", body="A time was proposed."),
        ])
        db.commit()
    rows = donor.get("/api/v2/notifications").json()
    assert len(rows) == 2 and sum(not row["read"] for row in rows) == 2
    marked = donor.post(f"/api/v2/notifications/{rows[0]['id']}/read")
    assert marked.status_code == 200 and marked.json()["read"] is True
    assert donor.get("/api/v2/notifications").json()[0]["read"] is True
    assert donor.post(f"/api/v2/notifications/{rows[1]['id']}/read").status_code == 200
    assert donor.post("/api/v2/notifications/read-all").json()["marked_read"] == 0

    assert institution.post("/api/v2/auth/signup", json={
        "name": "Other User", "email": "other-notice@test.local",
        "password": "school-password", "role": "org_member",
        "organisation_name": "Other School", "organisation_type": "school", "area": "Cidco"
    }).status_code == 201
    assert institution.get(f"/api/v2/notifications").json() == []
    assert institution.post(f"/api/v2/notifications/{rows[0]['id']}/read").status_code == 404


def test_owner_listing_management_and_status_transitions(clients):
    from backend.models import Organisation
    donor, institution, admin = clients
    assert donor.post("/api/v2/auth/signup", json={
        "name": "Listing Donor", "email": "listing-donor@test.local",
        "password": "donor-password", "role": "donor"
    }).status_code == 201
    donation = donor.post("/api/v2/donations", json={
        "category_id": 1, "title": "Unused notebooks", "condition": "good",
        "area": "Cidco", "quantity_total": 12
    }).json()
    own = donor.get("/api/v2/my-listings")
    assert own.status_code == 200 and len(own.json()) == 1
    assert own.json()[0]["quantity_remaining"] == 12

    # A different donor cannot see or edit someone else's listing.
    other, _, _ = clients
    other.post("/api/v2/auth/logout")
    assert other.post("/api/v2/auth/signup", json={
        "name": "Other Donor", "email": "other-listing@test.local",
        "password": "donor-password", "role": "donor"
    }).status_code == 201
    denied = other.patch(f"/api/v2/listings/donation/{donation['id']}", json={"title": "Hijacked"})
    assert denied.status_code == 404

    # Original owner can edit, pause and resume, then withdraw.
    donor.post("/api/v2/auth/logout")
    donor.post("/api/v2/auth/login", json={"email": "listing-donor@test.local", "password": "donor-password"})
    edited = donor.patch(f"/api/v2/listings/donation/{donation['id']}", json={
        "title": "Clean notebooks", "description": "Unused and in good condition",
        "area": "Garkheda", "quantity_total": 15
    })
    assert edited.status_code == 200 and edited.json()["title"] == "Clean notebooks"
    assert donor.post(f"/api/v2/listings/donation/{donation['id']}/status", json={"action": "pause"}).json()["status"] == "paused"
    assert donor.get("/api/v2/donations").json() == []
    assert donor.post(f"/api/v2/listings/donation/{donation['id']}/status", json={"action": "resume"}).json()["status"] == "active"
    assert donor.post(f"/api/v2/listings/donation/{donation['id']}/status", json={"action": "withdraw"}).json()["status"] == "withdrawn"

    # Institution-owned requirements use the same owner-scoped management API.
    assert institution.post("/api/v2/auth/signup", json={
        "name": "Listing School Owner", "email": "listing-school@test.local",
        "password": "school-password", "role": "org_member",
        "organisation_name": "Listing School", "organisation_type": "school", "area": "Cidco"
    }).status_code == 201
    org_id = institution.get("/api/v2/auth/me").json()["organisation"]["id"]
    with database.get_session_factory()() as db:
        org = db.get(Organisation, UUID(org_id)); org.verification_status = "verified"; db.commit()
    req = institution.post("/api/v2/requirements", json={
        "category_id": 1, "title": "Notebooks needed", "area": "Cidco", "quantity_requested": 20
    }).json()
    assert institution.get("/api/v2/my-listings").json()[0]["kind"] == "requirement"
    assert institution.patch(f"/api/v2/listings/requirement/{req['id']}", json={
        "title": "Notebooks for class 5", "quantity_requested": 24
    }).status_code == 200
    closed = institution.post(f"/api/v2/listings/requirement/{req['id']}/status", json={"action": "close"})
    assert closed.status_code == 200 and closed.json()["status"] == "closed"


def test_listing_edits_are_locked_while_offer_is_active(clients):
    from backend.models import Organisation
    donor, institution, admin = clients
    donor.post("/api/v2/auth/signup", json={"name": "Lock Donor", "email": "lock-donor@test.local", "password": "donor-password", "role": "donor"})
    donation = donor.post("/api/v2/donations", json={"category_id": 1, "title": "Pens", "condition": "good", "area": "Cidco", "quantity_total": 10}).json()
    institution.post("/api/v2/auth/signup", json={"name": "Lock School Owner", "email": "lock-school@test.local", "password": "school-password", "role": "org_member", "organisation_name": "Lock School", "organisation_type": "school", "area": "Cidco"})
    org_id = institution.get("/api/v2/auth/me").json()["organisation"]["id"]
    with database.get_session_factory()() as db:
        db.get(Organisation, UUID(org_id)).verification_status = "verified"
        db.commit()
    requirement = institution.post("/api/v2/requirements", json={"category_id": 1, "title": "Pens needed", "area": "Cidco", "quantity_requested": 8}).json()
    offer = donor.post("/api/v2/offers", json={"donation_id": donation["id"], "requirement_id": requirement["id"], "quantity": 4})
    assert offer.status_code == 201
    assert donor.patch(f"/api/v2/listings/donation/{donation['id']}", json={"title": "Changed after offer"}).status_code == 409
    paused = donor.post(f"/api/v2/listings/donation/{donation['id']}/status", json={"action": "pause"})
    assert paused.status_code == 409


def test_community_report_privacy_and_admin_resolution(clients):
    donor, reporter, admin = clients
    assert donor.post("/api/v2/auth/signup", json={
        "name": "Listing Owner", "email": "owner-report@test.local", "password": "owner-password", "role": "donor"
    }).status_code == 201
    listing = donor.post("/api/v2/donations", json={
        "category_id": 1, "title": "Reportable notebooks", "condition": "good", "area": "Cidco", "quantity_total": 4
    })
    assert listing.status_code == 201
    listing_id = listing.json()["id"]
    timeline = donor.get(f"/api/v2/listings/donation/{listing_id}/activity")
    assert timeline.status_code == 200
    assert any(entry["action"] == "donation.created" for entry in timeline.json())
    own_report = donor.post("/api/v2/reports", json={
        "target_type": "donation", "target_id": listing_id, "reason": "suspicious"
    })
    assert own_report.status_code == 403

    assert reporter.post("/api/v2/auth/signup", json={
        "name": "Concerned Member", "email": "reporter@test.local", "password": "reporter-password", "role": "donor"
    }).status_code == 201
    created = reporter.post("/api/v2/reports", json={
        "target_type": "donation", "target_id": listing_id, "reason": "misleading", "details": "The description appears inconsistent."
    })
    assert created.status_code == 201
    duplicate = reporter.post("/api/v2/reports", json={
        "target_type": "donation", "target_id": listing_id, "reason": "other"
    })
    assert duplicate.status_code == 409

    assert admin.post("/api/v2/auth/login", json={"email": "admin@test.local", "password": "admin-password"}).status_code == 200
    report_id = created.json()["id"]
    queue = admin.get("/api/v2/admin/reports")
    assert queue.status_code == 200
    assert queue.json()[0]["id"] == report_id
    assert queue.json()[0]["reporter"] == "Concerned Member"
    reviewed = admin.post(f"/api/v2/admin/reports/{report_id}", json={"action": "resolve", "note": "Reviewed against listing details."})
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "resolved"
    assert reporter.get("/api/v2/admin/reports").status_code == 403


def test_profiles_private_offer_contacts_and_admin_account_suspension(clients):
    donor, institution, admin = clients
    assert donor.post('/api/v2/auth/signup', json={
        'name': 'Profile Donor', 'email': 'profile-donor@test.local',
        'password': 'donor-password', 'role': 'donor'
    }).status_code == 201
    donor_profile = donor.patch('/api/v2/profile', json={'name': 'Updated Donor', 'phone': '+91 9876543210'})
    assert donor_profile.status_code == 200
    assert donor.get('/api/v2/profile').json()['phone'] == '+91 9876543210'

    assert institution.post('/api/v2/auth/signup', json={
        'name': 'Profile School Owner', 'email': 'profile-school@test.local',
        'password': 'school-password', 'role': 'org_member',
        'organisation_name': 'Profile School', 'organisation_type': 'school', 'area': 'Cidco'
    }).status_code == 201
    org_id = institution.get('/api/v2/auth/me').json()['organisation']['id']
    with database.get_session_factory()() as db:
        from backend.models import Organisation
        db.get(Organisation, UUID(org_id)).verification_status = 'verified'
        db.commit()
    assert institution.patch('/api/v2/profile', json={
        'organisation_name': 'Updated School', 'contact_phone': '+91 9000000000', 'description': 'A local school.'
    }).status_code == 200
    donation = donor.post('/api/v2/donations', json={
        'category_id': 1, 'title': 'School books', 'condition': 'good', 'area': 'Cidco', 'quantity_total': 5
    }).json()
    requirement = institution.post('/api/v2/requirements', json={
        'category_id': 1, 'title': 'Books needed', 'area': 'Cidco', 'quantity_requested': 3
    }).json()
    offer = donor.post('/api/v2/offers', json={
        'donation_id': donation['id'], 'requirement_id': requirement['id'], 'quantity': 2
    }).json()
    assert donor.get(f"/api/v2/offers/{offer['id']}/contacts").status_code == 409
    assert institution.post(f"/api/v2/offers/{offer['id']}/respond", json={'action': 'accept'}).status_code == 200
    contacts = donor.get(f"/api/v2/offers/{offer['id']}/contacts")
    assert contacts.status_code == 200
    assert contacts.json()['organisation'] == 'Updated School'
    assert contacts.json()['phone'] == '+91 9000000000'
    assert institution.get(f"/api/v2/offers/{offer['id']}/contacts").status_code == 200

    admin.post('/api/v2/auth/login', json={'email': 'admin@test.local', 'password': 'admin-password'})
    accounts = admin.get('/api/v2/admin/accounts')
    assert accounts.status_code == 200
    donor_id = donor.get('/api/v2/auth/me').json()['id']
    assert admin.post(f'/api/v2/admin/accounts/{donor_id}/status', json={'active': False}).json()['is_active'] is False
    assert donor.get('/api/v2/auth/me').json() is None
    assert donor.post('/api/v2/auth/login', json={'email': 'profile-donor@test.local', 'password': 'donor-password'}).status_code == 401
    assert admin.post(f'/api/v2/admin/accounts/{donor_id}/status', json={'active': True}).json()['is_active'] is True
    assert donor.post('/api/v2/auth/login', json={'email': 'profile-donor@test.local', 'password': 'donor-password'}).status_code == 200
