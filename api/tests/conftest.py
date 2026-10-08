from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from clipfarm_api import db, queue
from clipfarm_api.config import settings
from clipfarm_api.main import app

from sqlalchemy.pool import StaticPool

# Dossier temporaire pour tests
test_data_dir = Path(tempfile.mkdtemp(prefix="clipfarm_test_data_"))
settings.data_dir = test_data_dir
settings.upload_dir = test_data_dir / "uploads"
settings.upload_dir.mkdir(parents=True, exist_ok=True)

# Engine SQLite en mémoire partagée
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Remplacer globalement les engines pour les tests
db.engine = test_engine
queue.engine = test_engine


@pytest.fixture(name="session", autouse=True)
def session_fixture() -> Generator[Session, None, None]:
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def get_session_override():
        return session

    app.dependency_overrides[db.get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
