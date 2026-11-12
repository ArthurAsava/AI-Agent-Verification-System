
from app.services.verification.decision_contracts import (
    Recommendation,
    VerificationRecommendation,
)
from app.services.verification.risk_engine import (
    RiskEngineResult,
)


def build_recommendation(
    result: RiskEngineResult,
    document_analysis_passed: bool,
) -> VerificationRecommendation:

    if not isinstance(result, RiskEngineResult):
        raise ValueError("Invalid risk engine result.")

    if type(document_analysis_passed) is not bool:
        raise ValueError("Invalid analysis status.")

    risk = result.risk
    codes = tuple(
        indicator.code
        for indicator in result.indicators
    )

    if risk.level in ("high", "critical"):
        recommendation = Recommendation.ESCALATE

    elif (
        document_analysis_passed
        and not result.requires_review
        and risk.level == "low"
    ):
        recommendation = Recommendation.RECOMMEND_PASS

    else:
        recommendation = Recommendation.MANUAL_REVIEW

    return VerificationRecommendation(
        recommendation=recommendation,
        risk_score=risk.score,
        risk_level=risk.level,
        reason_codes=codes,
        requires_human_review=True,
    )
