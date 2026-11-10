"""
Integration and functional tests for FastAPI API endpoints.

Tests:
- Health check
- Authentication (registration, login, token refresh, current user profile)
- Input validation (malformed email, weak password)
- Access control & RBAC (admin endpoints require admin role)
- Public verification (attestation lookup)
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import get_settings
from backend.app.core.database import Base, get_db
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
from backend.app.models.models import User

# In-memory SQLite async engine for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    future=True,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    """Create all tables in the test SQLite database before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


def user_token(user: User) -> str:
    settings = get_settings()
    return create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role},
        secret_key=settings.jwt_secret_key,
    )


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def regular_user() -> User:
    """Seed a regular user in the test database."""
    async with TestSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email="testuser@example.com",
            display_name="Test User",
            password_hash=hash_password("SecurePassword123!"),
            role="user",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def admin_user() -> User:
    """Seed an admin user in the test database."""
    async with TestSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            display_name="Admin User",
            password_hash=hash_password("AdminSecurePassword123!"),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ═══════════════════════════════════════════════════════════════
# Health Endpoint
# ═══════════════════════════════════════════════════════════════

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


# ═══════════════════════════════════════════════════════════════
# Auth Endpoints
# ═══════════════════════════════════════════════════════════════

def test_register_success(client):
    payload = {
        "email": "newuser@example.com",
        "display_name": "New User",
        "password": "Password1234!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["display_name"] == "New User"
    assert data["role"] == "user"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_email(client, regular_user):
    payload = {
        "email": regular_user.email,
        "display_name": "Duplicate User",
        "password": "Password1234!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


def test_register_invalid_email(client):
    payload = {
        "email": "not-an-email",
        "display_name": "Invalid Email",
        "password": "Password1234!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422


def test_register_short_password(client):
    payload = {
        "email": "valid@example.com",
        "display_name": "Short Password",
        "password": "short",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422


def test_login_success(client, regular_user):
    payload = {
        "email": "testuser@example.com",
        "password": "SecurePassword123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_invalid_password(client, regular_user):
    payload = {
        "email": "testuser@example.com",
        "password": "WrongPassword123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    payload = {
        "email": "nobody@example.com",
        "password": "Password1234!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401


def test_get_current_user_profile(client, regular_user):
    token = user_token(regular_user)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(regular_user.id)
    assert data["email"] == regular_user.email
    assert data["role"] == "user"


def test_get_current_user_unauthorized(client):
    response = client.get("/auth/me")
    assert response.status_code in (401, 403)


def test_refresh_token(client, regular_user):
    login_resp = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "SecurePassword123!",
    })
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


# ═══════════════════════════════════════════════════════════════
# RBAC & Admin Endpoints
# ═══════════════════════════════════════════════════════════════

def test_admin_keys_unauthorized(client):
    response = client.get("/admin/keys")
    assert response.status_code in (401, 403)


def test_admin_keys_forbidden_for_regular_user(client, regular_user):
    token = user_token(regular_user)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/admin/keys", headers=headers)
    assert response.status_code == 403


def test_admin_keys_allowed_for_admin(client, admin_user):
    token = user_token(admin_user)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/admin/keys", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "Ed25519"
    assert "public_key_pem" in data
    assert "key_id" in data


def test_admin_anomalies_forbidden_for_regular_user(client, regular_user):
    token = user_token(regular_user)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/admin/anomalies", headers=headers)
    assert response.status_code == 403


# ═══════════════════════════════════════════════════════════════
# Public Verification Endpoints
# ═══════════════════════════════════════════════════════════════

def test_verify_by_id_not_found(client):
    random_id = str(uuid.uuid4())
    response = client.post("/verify/by-id", json={"attestation_id": random_id})
    assert response.status_code == 404
