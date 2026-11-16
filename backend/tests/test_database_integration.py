
import os

import pytest
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Live database tests require RUN_DB_TESTS=1",
)


SECURED_PUBLIC_TABLES = {
    "agents",
    "agent_onboarding",
    "kyc_documents",
    "verification_checks",
    "verification_cases",
    "verification_reviewers",
    "fraud_assessments",
    "audit_logs",
    "alembic_version",
}


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
              AND tablename = ANY(:tables)
        """),
        {"tables": list(SECURED_PUBLIC_TABLES)},
    ).all()

    assert {row.tablename for row in rows} == SECURED_PUBLIC_TABLES
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
        "audit_logs_block_direct_api_access",
        "fraud_assessments_block_direct_api_access",
        "verification_reviewers_block_direct_api_access",
        "alembic_version_block_direct_api_access",
    }.issubset(set(rows))


def test_client_roles_have_no_direct_public_table_privileges(connection):
    rows = connection.execute(
        text("""
            SELECT table_name, grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND table_name = ANY(:tables)
              AND grantee IN ('PUBLIC', 'anon', 'authenticated')
        """),
        {"tables": list(SECURED_PUBLIC_TABLES)},
    ).all()

    assert rows == []


def test_database_migration_applied(connection):
    revision = connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one_or_none()

    assert revision is not None
