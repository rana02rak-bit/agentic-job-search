from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_existing_schema()


def _migrate_existing_schema() -> None:
    inspector = inspect(engine)
    if "recruiters" not in inspector.get_table_names():
        return
    recruiter_columns = {column["name"] for column in inspector.get_columns("recruiters")}
    outreach_columns = {
        column["name"] for column in inspector.get_columns("outreach_messages")
    }
    recruiter_additions = {
        "email": "VARCHAR(320)",
        "email_status": "VARCHAR(32)",
        "source": "VARCHAR(32) DEFAULT 'MANUAL'",
        "external_id": "VARCHAR(160)",
    }
    outreach_additions = {
        "subject": "VARCHAR(240)",
        "recipient_email": "VARCHAR(320)",
        "provider_message_id": "VARCHAR(500)",
        "provider_thread_id": "VARCHAR(500)",
    }
    with engine.begin() as connection:
        for column, definition in recruiter_additions.items():
            if column not in recruiter_columns:
                connection.execute(
                    text(f"ALTER TABLE recruiters ADD COLUMN {column} {definition}")
                )
        for column, definition in outreach_additions.items():
            if column not in outreach_columns:
                connection.execute(
                    text(f"ALTER TABLE outreach_messages ADD COLUMN {column} {definition}")
                )
        if engine.dialect.name == "postgresql":
            connection.execute(
                text("ALTER TABLE recruiters ALTER COLUMN linkedin_url DROP NOT NULL")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_recruiter_company_email_idx "
                    "ON recruiters (company_id, email) WHERE email IS NOT NULL"
                )
            )
