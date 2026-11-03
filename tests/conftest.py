import os
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("ENVIRONMENT", "test")
# Pin reminder timings so a local .env tuned for manual testing can't break tests.
os.environ["WATER_REMINDER_THRESHOLD_MINUTES"] = "90"
os.environ["WATER_SNOOZE_MINUTES"] = "60"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.constants import ActivityLevel, DietPreference, Gender, Goal
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.schemas.user import SignupRequest
from app.services import auth_service
from app.services.storage import factory
from app.services.storage.local import LocalFilesystemStorage

TEST_DB_PATH = Path(__file__).parent / "test.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def photo_storage(tmp_path, monkeypatch):
    """Save meal photos to a temp folder, never the real media/ folder or S3."""
    storage = LocalFilesystemStorage(str(tmp_path / "media"))
    monkeypatch.setattr(factory, "get_storage", lambda name: storage)
    return storage


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        # Don't unlink the file here: SQLAlchemy's connection pool may still hold an
        # open handle on Windows, which makes os.remove raise WinError 32. Dropping
        # tables is enough isolation between tests; the (now-empty) file is removed
        # once at session end, after the engine is fully disposed (see below).


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_signup_payload(**overrides) -> SignupRequest:
    defaults = dict(
        email="user@example.com",
        password="supersecret123",
        preferred_name="Test User",
        age=28,
        gender=Gender.MALE,
        height_cm=175,
        weight_kg=70,
        medical_conditions=[],
        goal=Goal.LOSE_WEIGHT,
        diet_preference=DietPreference.VEG,
        activity_level=ActivityLevel.MODERATE,
        daily_budget=500,
        monthly_budget=15000,
        timezone="Asia/Kolkata",
    )
    defaults.update(overrides)
    return SignupRequest(**defaults)


@pytest.fixture()
def test_user(db_session) -> User:
    return auth_service.signup(db_session, make_signup_payload())


@pytest.fixture()
def auth_headers(test_user: User) -> dict:
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_user(db_session) -> User:
    user = auth_service.signup(db_session, make_signup_payload(email="admin@example.com"))
    user.is_admin = True
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_auth_headers(admin_user: User) -> dict:
    token = create_access_token(admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def long_lived_auth_headers(test_user: User, monkeypatch) -> dict:
    """For tests that use freezegun to fast-forward hours of simulated time: a
    normal 30-minute access token would expire mid-test for reasons unrelated to
    what's under test, so this issues one that outlives the simulated time jump."""
    from app.core import security

    monkeypatch.setattr(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24)
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db_file():
    yield
    test_engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
