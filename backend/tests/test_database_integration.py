
import os

import pytest
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Live database tests require RUN_DB_TESTS=1",
)


@pytest.fixture(scope="module")
def connection():
    from app.core.config import get_settings

    url = get_settings().DATABASE_URL

    if not url:
        pytest.fail("DATABASE_URL is missing")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.connect() as conn:
            yield conn
    finally:
        engine.dispose()


def test_database_connection(connection):
    assert connection.execute(
        text("SELECT 1")
    ).scalar_one() == 1


def test_application_tables_exist(connection):
    inspector = inspect(connection)
    actual = set(inspector.get_table_names(schema="public"))

    expected = {
        "agents",
        "kyc_documents",
        "verification_checks",
        "fraud_assessments",
        "audit_logs",
    }

    assert expected.issubset(actual)


def test_rls_enabled_on_all_tables(connection):
    rows = connection.execute(
        text("""
            SELECT tablename, rowsecurity
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename IN (
                  'agents',
                  'kyc_documents',
                  'verification_checks',
                  'fraud_assessments',
                  'audit_logs'
              )
        """)
    ).all()

    assert len(rows) == 5
    assert all(row.rowsecurity for row in rows)


def test_expected_rls_policies_exist(connection):
    rows = connection.execute(
        text("""
            SELECT policyname
            FROM pg_policies
            WHERE schemaname = 'public'
        """)
    ).scalars().all()

    assert {
        "agents_select_own",
        "documents_select_own",
        "checks_select_own",
    }.issubset(set(rows))


def test_database_migration_applied(connection):
    revision = connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one_or_none()

    assert revision is not None
