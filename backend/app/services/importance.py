"""Canonical DNO importance scoring.

Purpose:
- Provide a deterministic, explainable importance score (0-100) for each DNO.
- Handle sparse source data safely by using explicit fallbacks and confidence tracking.

Current v1 inputs:
- service area (km²)       -> optional, currently often missing
- connection points count  -> primary signal (MaStR)
- customer count           -> optional, may be absent for transmission operators

If area/customer count are missing, we do not fail scoring. We apply conservative
fallback factors and record this in the explainability payload.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from math import log1p

IMPORTANCE_VERSION = "v1"

# Dominant weighting on connection points as requested.
WEIGHTS = {
    "area": 0.15,
    "connection_points": 0.70,
    "customers": 0.15,
}

# Calibration anchors; can be overridden by runtime calibration.
DEFAULT_CALIBRATION = {
    "area_km2_p90": 1500.0,
    "connection_points_p90": 20000.0,
    "customer_count_p90": 500000.0,
}

# Conservative neutral values when no direct measure exists.
DEFAULT_FALLBACK_FACTORS = {
    "area": 0.25,
    "customers": 0.10,
}


@dataclass(frozen=True, slots=True)
class ImportanceInputs:
    """Raw inputs used for importance scoring."""

    connection_points: int | None
    customer_count: int | None
    has_customers: bool | None
    area_km2: float | None


@dataclass(frozen=True, slots=True)
class ImportanceResult:
    """Computed score and explainability payload."""

    score: float
    confidence: float
    version: str
    factors: dict


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalize_log(raw_value: float | int | None, p90: float) -> float | None:
    if raw_value is None:
        return None
    value = float(raw_value)
    if value <= 0:
        return 0.0
    denom = log1p(max(p90, 1.0))
    if denom <= 0:
        return 0.0
    return _clip(log1p(value) / denom)


def _factor_with_fallback(
    *,
    normalized: float | None,
    fallback: float,
) -> tuple[float, bool]:
    if normalized is None:
        return fallback, True
    return normalized, False


def _customer_factor(inputs: ImportanceInputs, calibration: dict[str, float]) -> tuple[float, dict]:
    normalized = _normalize_log(inputs.customer_count, calibration["customer_count_p90"])
    if normalized is not None:
        return normalized, {
            "source": "customer_count",
            "raw": inputs.customer_count,
            "normalized": normalized,
            "is_fallback": False,
        }

    if inputs.has_customers is False:
        return 0.0, {
            "source": "has_customers_false",
            "raw": None,
            "normalized": 0.0,
            "is_fallback": True,
            "note": "No direct customers reported",
        }

    if inputs.has_customers is True:
        # Known to have customers, but count unknown.
        return 0.35, {
            "source": "has_customers_true",
            "raw": None,
            "normalized": 0.35,
            "is_fallback": True,
            "note": "Has customers, but customer count missing",
        }

    return DEFAULT_FALLBACK_FACTORS["customers"], {
        "source": "default_fallback",
        "raw": None,
        "normalized": DEFAULT_FALLBACK_FACTORS["customers"],
        "is_fallback": True,
        "note": "Customer data unavailable",
    }


def compute_importance(
    inputs: ImportanceInputs,
    *,
    calibration: dict[str, float] | None = None,
) -> ImportanceResult:
    """Compute canonical importance score and explainability payload."""
    calibration_data = calibration or DEFAULT_CALIBRATION

    area_normalized = _normalize_log(inputs.area_km2, calibration_data["area_km2_p90"])
    area_factor, area_fallback = _factor_with_fallback(
        normalized=area_normalized,
        fallback=DEFAULT_FALLBACK_FACTORS["area"],
    )

    connection_normalized = _normalize_log(
        inputs.connection_points,
        calibration_data["connection_points_p90"],
    )
    connection_factor = connection_normalized if connection_normalized is not None else 0.0
    connection_fallback = connection_normalized is None

    customer_factor, customer_meta = _customer_factor(inputs, calibration_data)

    area_contribution = WEIGHTS["area"] * area_factor
    connection_contribution = WEIGHTS["connection_points"] * connection_factor
    customer_contribution = WEIGHTS["customers"] * customer_factor

    score = round((area_contribution + connection_contribution + customer_contribution) * 100, 2)

    fallback_count = sum([area_fallback, connection_fallback, customer_meta["is_fallback"]])
    confidence = round(_clip(1.0 - (fallback_count / 3.0) * 0.6), 2)

    factors = {
        "weights": WEIGHTS,
        "calibration": calibration_data,
        "inputs": {
            "area_km2": inputs.area_km2,
            "connection_points": inputs.connection_points,
            "customer_count": inputs.customer_count,
            "has_customers": inputs.has_customers,
        },
        "normalized": {
            "area": area_factor,
            "connection_points": connection_factor,
            "customers": customer_factor,
        },
        "contributions": {
            "area": round(area_contribution * 100, 2),
            "connection_points": round(connection_contribution * 100, 2),
            "customers": round(customer_contribution * 100, 2),
        },
        "fallbacks": {
            "area": area_fallback,
            "connection_points": connection_fallback,
            "customers": customer_meta["is_fallback"],
        },
        "customer_factor_meta": customer_meta,
        "computed_at": datetime.now(UTC).isoformat(),
    }

    return ImportanceResult(
        score=score,
        confidence=confidence,
        version=IMPORTANCE_VERSION,
        factors=factors,
    )


def compute_importance_for_dno(dno: object) -> ImportanceResult:
    """Compute importance from a DNO ORM object with optional MaStR relation."""
    mastr_data = getattr(dno, "mastr_data", None)

    connection_points = getattr(dno, "connection_points_count", None)
    if connection_points is None and mastr_data is not None:
        connection_points = getattr(mastr_data, "connection_points_total", None)

    customer_count = getattr(dno, "customer_count", None)
    has_customers = getattr(mastr_data, "has_customers", None) if mastr_data is not None else None
    area_km2 = getattr(dno, "service_area_km2", None)

    return compute_importance(
        ImportanceInputs(
            connection_points=connection_points,
            customer_count=customer_count,
            has_customers=has_customers,
            area_km2=area_km2,
        )
    )


def apply_importance_to_dno(dno: object) -> ImportanceResult:
    """Compute and assign importance fields on a DNO ORM instance."""
    result = compute_importance_for_dno(dno)
    dno.importance_score = result.score
    dno.importance_confidence = result.confidence
    dno.importance_version = result.version
    dno.importance_factors = result.factors
    dno.importance_updated_at = datetime.now(UTC)
    return result
