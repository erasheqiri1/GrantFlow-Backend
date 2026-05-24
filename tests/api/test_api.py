"""
API teste për GrantFlow — testojnë endpoint-et HTTP.
Përdorin TestClient nga FastAPI (pa nevojë për server të vërtetë).
DB-ja është e mock-uar — testet punojnë edhe pa PostgreSQL.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db

# ──────────────────────────────────────────────
# Mock DB — shmang nevojën për PostgreSQL real
# ──────────────────────────────────────────────
def override_get_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    yield db

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app, raise_server_exceptions=False)


# ══════════════════════════════════════════════
# 1. HEALTH CHECK
# ══════════════════════════════════════════════
class TestHealthCheck:
    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_ok_status(self):
        response = client.get("/")
        assert response.json()["status"] == "ok"

    def test_root_contains_app_name(self):
        response = client.get("/")
        assert "GrantFlow" in response.json()["app"]


# ══════════════════════════════════════════════
# 2. AUTH — REGJISTRIM
# ══════════════════════════════════════════════
class TestRegisterApplicant:
    def test_register_missing_fields_returns_422(self):
        response = client.post("/auth/register", json={})
        assert response.status_code == 422

    def test_register_invalid_email_returns_422(self):
        response = client.post("/auth/register", json={
            "first_name": "Era",
            "last_name":  "Sheqiri",
            "email":      "nuk-eshte-email",
            "password":   "Secret123!"
        })
        assert response.status_code == 422

    def test_register_missing_password_returns_422(self):
        response = client.post("/auth/register", json={
            "first_name": "Era",
            "last_name":  "Sheqiri",
            "email":      "era@test.com"
        })
        assert response.status_code == 422

    def test_register_missing_first_name_returns_422(self):
        response = client.post("/auth/register", json={
            "last_name": "Sheqiri",
            "email":     "era@test.com",
            "password":  "Secret123!"
        })
        assert response.status_code == 422


class TestRegisterOrg:
    def test_register_org_missing_fields_returns_422(self):
        response = client.post("/auth/register-org", json={})
        assert response.status_code == 422

    def test_register_org_invalid_email_returns_422(self):
        response = client.post("/auth/register-org", json={
            "first_name": "Era",
            "last_name":  "Sheqiri",
            "email":      "jo-email",
            "password":   "Secret123!",
            "org_name":   "Org Test",
            "org_slug":   "org-test"
        })
        assert response.status_code == 422


# ══════════════════════════════════════════════
# 3. AUTH — LOGIN
# ══════════════════════════════════════════════
class TestLogin:
    def test_login_missing_fields_returns_422(self):
        response = client.post("/auth/login", json={})
        assert response.status_code == 422

    def test_login_invalid_email_format_returns_422(self):
        response = client.post("/auth/login", json={
            "email":    "nuk-eshte-email",
            "password": "secret"
        })
        assert response.status_code == 422

    def test_login_missing_password_returns_422(self):
        response = client.post("/auth/login", json={
            "email": "test@test.com"
        })
        assert response.status_code == 422


# ══════════════════════════════════════════════
# 4. AUTH — FORGOT PASSWORD
# ══════════════════════════════════════════════
class TestForgotPassword:
    def test_forgot_password_missing_email_returns_422(self):
        response = client.post("/auth/forgot-password", json={})
        assert response.status_code == 422

    def test_forgot_password_invalid_email_returns_422(self):
        response = client.post("/auth/forgot-password", json={
            "email": "nuk-eshte-email"
        })
        assert response.status_code == 422


# ══════════════════════════════════════════════
# 5. ENDPOINT-ET E MBROJTURA — PA TOKEN → 401
# ══════════════════════════════════════════════
class TestProtectedEndpoints:
    """Krejt këto endpoint-e duhet të kthejnë 401 pa token."""

    def test_get_grants_without_token_returns_401(self):
        response = client.get("/grants")
        assert response.status_code == 401

    def test_create_grant_without_token_returns_401(self):
        response = client.post("/grants", json={"title": "Test"})
        assert response.status_code == 401

    def test_get_applications_without_token_returns_401(self):
        response = client.get("/applications")
        assert response.status_code == 401

    def test_create_application_without_token_returns_401(self):
        response = client.post("/applications", json={})
        assert response.status_code == 401

    def test_get_my_applications_without_token_returns_401(self):
        response = client.get("/applications/my")
        assert response.status_code == 401

    def test_get_profile_without_token_returns_401(self):
        response = client.get("/profile")
        assert response.status_code == 401

    def test_get_tenants_without_token_returns_401(self):
        response = client.get("/tenants")
        assert response.status_code == 401

    def test_get_team_without_token_returns_401(self):
        response = client.get("/team")
        assert response.status_code == 401

    def test_get_users_without_token_returns_401(self):
        response = client.get("/users")
        assert response.status_code == 401

    def test_get_audit_logs_without_token_returns_401(self):
        response = client.get("/audit")
        assert response.status_code == 401


# ══════════════════════════════════════════════
# 6. TOKEN I RREMË → 401
# ══════════════════════════════════════════════
class TestFakeToken:
    """Token i rremë duhet të kthehet 401."""

    FAKE_HEADERS = {"Authorization": "Bearer token.i.rreme"}

    def test_fake_token_on_grants_returns_401(self):
        response = client.get("/grants", headers=self.FAKE_HEADERS)
        assert response.status_code == 401

    def test_fake_token_on_applications_returns_401(self):
        response = client.get("/applications", headers=self.FAKE_HEADERS)
        assert response.status_code == 401

    def test_fake_token_on_profile_returns_401(self):
        response = client.get("/profile", headers=self.FAKE_HEADERS)
        assert response.status_code == 401


# ══════════════════════════════════════════════
# 7. VERIFY EMAIL — VALIDIM
# ══════════════════════════════════════════════
class TestVerifyEmail:
    def test_verify_email_without_token_returns_422(self):
        response = client.get("/auth/verify-email")
        assert response.status_code == 422

    def test_verify_email_is_public_path(self):
        """Verify-email duhet të jetë i aksesueshëm pa JWT (jo 401)."""
        response = client.get("/auth/verify-email?token=tok_fake")
        assert response.status_code != 401


# ══════════════════════════════════════════════
# 8. SWAGGER DOCS
# ══════════════════════════════════════════════
class TestDocs:
    def test_swagger_ui_accessible(self):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_accessible(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_has_title(self):
        response = client.get("/openapi.json")
        assert response.json()["info"]["title"] == "GrantFlow API"
