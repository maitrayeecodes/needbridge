import pytest
from backend import auth, matching


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    monkeypatch.setattr(matching, "DATA_DIR", tmp_path)  # every test gets its own empty database


def test_password_is_hashed_and_verifies():
    stored = auth.hash_password("correct horse")
    assert "correct horse" not in stored
    assert auth.verify_password("correct horse", stored)
    assert not auth.verify_password("wrong", stored)


def test_signup_validates_everything():
    _, errors = auth.create_user("A", "not-an-email", "short", "boss")
    assert len(errors) == 4


def test_cannot_sign_up_as_admin():
    user, errors = auth.create_user("Mallory", "m@x.com", "longpassword", "admin")
    assert user is None and errors


def test_admin_can_be_created_from_the_command_line_path():
    user, errors = auth.create_user("Admin", "a@x.com", "longpassword", "admin", allow_admin=True)
    assert not errors and user["role"] == "admin"


def test_duplicate_email_is_rejected_ignoring_case():
    auth.create_user("Anu", "anu@x.com", "longpassword", "donor", "cidco")
    user, errors = auth.create_user("Anu Two", "ANU@x.com", "longpassword", "donor")
    assert user is None and "already exists" in errors[0]


def test_login_works_only_with_the_right_password():
    auth.create_user("Anu", "anu@x.com", "longpassword", "donor", "cidco")
    assert auth.check_login("ANU@x.com", "longpassword")["name"] == "Anu"
    assert auth.check_login("anu@x.com", "wrongpassword") is None
    assert auth.check_login("nobody@x.com", "longpassword") is None