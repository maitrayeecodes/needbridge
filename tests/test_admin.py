import pandas as pd
import pytest
from backend import api, auth, matching

HEADER = "request_id,organization,category,item,quantity_needed,age_min,age_max,area,verified\r\n"


@pytest.fixture(autouse=True)
def temp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(matching, "DATA_DIR", tmp_path)
    (tmp_path / "requests.csv").write_text(HEADER + "R01,A School,notebooks,N,10,6,9,Cidco,no\r\nR02,B NGO,school_bag,B,5,6,9,Garkheda,yes\r\n")
    return tmp_path


def test_approve_and_reject_change_only_that_request(temp_data):
    f = temp_data / "requests.csv"
    assert api.set_verified(f, "R01", "yes")
    assert api.set_verified(f, "R02", "rejected")
    df = pd.read_csv(f).set_index("request_id")
    assert df.loc["R01", "verified"] == "yes" and df.loc["R02", "verified"] == "rejected"
    assert df.loc["R01", "organization"] == "A School"


def test_unknown_request_is_reported(temp_data):
    assert api.set_verified(temp_data / "requests.csv", "R99", "yes") is False


def test_fresh_disk_gets_sample_data(tmp_path, monkeypatch):
    empty = tmp_path / "fresh"
    monkeypatch.setattr(matching, "DATA_DIR", empty)
    api.seed_data()
    assert (empty / "donations.csv").exists() or not (api.ROOT / "data" / "donations.csv").exists()


def test_admin_account_is_created_from_environment_once(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@x.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "longpassword")
    api.ensure_admin()
    api.ensure_admin()  # second call must not fail or duplicate
    assert auth.check_login("boss@x.com", "longpassword")["role"] == "admin"