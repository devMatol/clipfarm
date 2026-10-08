from __future__ import annotations

from typing import Generator
from sqlmodel import Session, SQLModel, create_engine
from .config import settings

# Connect args if sqlite
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
)


def init_db(custom_engine=None) -> None:
    target = custom_engine or engine
    try:
        SQLModel.metadata.create_all(target)
    except Exception as exc:
        import logging
        logging.getLogger("clipfarm_db").warning("init_db impossible (Postgres non joignable?): %s", exc)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
