
import jwt
import pytest
from app.services.auth import hash_password, verify_password, create_token
from app.core.config import settings


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        hashed = hash_password("secret123")
        assert isinstance(hashed, str)

    def test_hash_is_different_from_original(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"

    def test_verify_correct_password(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong_password", hashed) is False

    def test_same_password_different_hash(self):
        """bcrypt gjeneron hash të ndryshëm cdo herë"""
        h1 = hash_password("secret123")
        h2 = hash_password("secret123")
        assert h1 != h2


class TestCreateToken:
    def test_token_is_string(self):
        token = create_token("user-123", "ORG_ADMIN", "test_org")
        assert isinstance(token, str)

    def test_token_contains_correct_payload(self):
        token = create_token("user-123", "ORG_ADMIN", "test_org")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert payload["user_id"] == "user-123"
        assert payload["role"] == "ORG_ADMIN"
        assert payload["tenant_slug"] == "test_org"

    def test_token_has_expiry(self):
        token = create_token("user-123", "ORG_ADMIN", "test_org")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert "exp" in payload

    def test_different_roles_produce_different_tokens(self):
        t1 = create_token("user-123", "ORG_ADMIN", "test_org")
        t2 = create_token("user-123", "COMMISSIONER", "test_org")
        assert t1 != t2
