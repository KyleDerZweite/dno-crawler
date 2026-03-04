"""Tests for canonical DNO importance scoring."""

from app.services.importance import ImportanceInputs, compute_importance


def test_importance_prioritizes_connection_points() -> None:
    low = compute_importance(
        ImportanceInputs(
            connection_points=100,
            customer_count=None,
            has_customers=False,
            area_km2=None,
        )
    )
    high = compute_importance(
        ImportanceInputs(
            connection_points=10000,
            customer_count=None,
            has_customers=False,
            area_km2=None,
        )
    )

    assert high.score > low.score


def test_importance_handles_no_direct_customers() -> None:
    result = compute_importance(
        ImportanceInputs(
            connection_points=500,
            customer_count=None,
            has_customers=False,
            area_km2=None,
        )
    )

    assert result.score >= 0
    assert result.factors["customer_factor_meta"]["source"] == "has_customers_false"


def test_importance_uses_customer_count_when_available() -> None:
    without_customers = compute_importance(
        ImportanceInputs(
            connection_points=2000,
            customer_count=None,
            has_customers=False,
            area_km2=None,
        )
    )
    with_customers = compute_importance(
        ImportanceInputs(
            connection_points=2000,
            customer_count=120000,
            has_customers=True,
            area_km2=None,
        )
    )

    assert with_customers.score > without_customers.score
    assert with_customers.factors["customer_factor_meta"]["is_fallback"] is False
