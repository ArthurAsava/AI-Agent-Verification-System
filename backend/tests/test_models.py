
from sqlalchemy import inspect

from app.core.database import Base
import app.models
from app.models.verification_case import VerificationCase


EXPECTED_TABLES = {
    "agents",
    "kyc_documents",
    "verification_checks",
    "fraud_assessments",
    "audit_logs",
     "agent_onboarding",
     "verification_cases",
     "verification_reviewers",
}


def test_all_application_tables_registered():
    tables = {
        table.name
        for table in Base.metadata.tables.values()
        if table.schema is None
    }

    assert tables == EXPECTED_TABLES


def test_agent_user_id_is_unique():
    agents = Base.metadata.tables["agents"]

    assert agents.c.user_id.unique is True


def test_document_references_agent():
    documents = Base.metadata.tables["kyc_documents"]

    foreign_keys = {
        fk.target_fullname
        for fk in documents.foreign_keys
    }

    assert "agents.id" in foreign_keys


def test_agent_references_supabase_auth():
    agents = Base.metadata.tables["agents"]

    foreign_keys = {
        fk.target_fullname
        for fk in agents.foreign_keys
    }

    assert "auth.users.id" in foreign_keys


def test_fraud_score_has_range_constraint():
    assessments = Base.metadata.tables["fraud_assessments"]

    constraints = {
        constraint.name
        for constraint in assessments.constraints
    }

    assert "risk_score_range" in constraints
