"""
Voltage Level-Based Completeness Scoring for DNOs.

Compares expected data coverage (from MaStR voltage level statistics)
against actually extracted Netzentgelte/HLZF records to produce a
meaningful completeness score.

Design decisions:
- Pure functions operating on data, not DB-aware (caller provides inputs).
- No I/O: the caller fetches from DB, this module scores.
- Transformer voltage levels (e.g. HS/MS) are expected when both sides
  have connection points, matching real-world DNO publishing behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import VOLTAGE_LEVELS

# ─── Mapping: MaStR connection-point buckets → voltage levels ─────────────────
# MaStR tracks NS, MS, HS, HöS connection points.  For each bucket with
# connection points > 0, the DNO is expected to publish data for that level
# AND the transformer level below it (e.g. HS > 0 → expect "HS" + "HS/MS").
#
# The transformer ("Umspannung") level sits between two primary levels and
# is where power is transformed from the higher to lower voltage.

_MASTR_BUCKET_TO_LEVELS: dict[str, list[str]] = {
    "ns": ["NS"],
    "ms": ["MS", "MS/NS"],
    "hs": ["HS", "HS/MS"],
    "hoe": ["HöS", "HöS/HS"],
}


@dataclass(frozen=True, slots=True)
class VoltageExpectation:
    """Which voltage level is expected and whether we have data for it."""

    level: str
    expected: bool
    has_netzentgelte: bool
    has_hlzf: bool

    @property
    def covered(self) -> bool:
        """Level is covered if we have at least netzentgelte data."""
        return self.has_netzentgelte


@dataclass(frozen=True, slots=True)
class CompletenessScore:
    """Full completeness breakdown for a single DNO + year."""

    # Overall percentage (0–100). None when expectations can't be computed.
    score: int | None
    # Per-level breakdown, ordered highest → lowest voltage.
    levels: list[VoltageExpectation] = field(default_factory=list)
    # Number of expected and covered levels.
    expected_count: int = 0
    covered_count: int = 0
    # Whether MaStR data was available to compute expectations.
    has_expectations: bool = False


def expected_voltage_levels(
    connection_points: dict[str, int | None],
) -> list[str]:
    """Derive which voltage levels a DNO is expected to publish.

    Args:
        connection_points: Mapping of MaStR bucket name to count.
            Keys: "ns", "ms", "hs", "hoe".  Values may be None/0.

    Returns:
        Deduplicated sorted list of expected voltage levels (highest first).
    """
    expected: set[str] = set()

    for bucket, levels in _MASTR_BUCKET_TO_LEVELS.items():
        count = connection_points.get(bucket) or 0
        if count > 0:
            expected.update(levels)

    # Sort in canonical order (highest voltage first)
    ordered = [lvl for lvl in VOLTAGE_LEVELS if lvl in expected]
    return ordered


def compute_completeness(
    connection_points: dict[str, int | None] | None,
    actual_netzentgelte_levels: set[str],
    actual_hlzf_levels: set[str],
) -> CompletenessScore:
    """Compute completeness score for a DNO.

    Args:
        connection_points: MaStR connection point counts per bucket
            (keys: ns, ms, hs, hoe). Pass None when MaStR data unavailable.
        actual_netzentgelte_levels: Set of voltage level strings for which
            the DNO has at least one Netzentgelte record.
        actual_hlzf_levels: Set of voltage level strings for which the DNO
            has at least one HLZF record.

    Returns:
        CompletenessScore with per-level detail and overall percentage.
    """
    # When MaStR data is missing, fall back to a simple presence check
    if connection_points is None:
        has_any = bool(actual_netzentgelte_levels or actual_hlzf_levels)
        return CompletenessScore(
            score=100 if has_any else 0,
            has_expectations=False,
        )

    expected = expected_voltage_levels(connection_points)

    if not expected:
        # No connection points at all — DNO might be inactive.
        # If they still publish data, give full score; otherwise 0.
        has_any = bool(actual_netzentgelte_levels or actual_hlzf_levels)
        return CompletenessScore(
            score=100 if has_any else 0,
            has_expectations=False,
        )

    levels: list[VoltageExpectation] = []
    covered = 0

    for lvl in expected:
        has_netz = lvl in actual_netzentgelte_levels
        has_hlzf = lvl in actual_hlzf_levels
        ve = VoltageExpectation(
            level=lvl,
            expected=True,
            has_netzentgelte=has_netz,
            has_hlzf=has_hlzf,
        )
        if ve.covered:
            covered += 1
        levels.append(ve)

    score = round((covered / len(expected)) * 100) if expected else 0

    return CompletenessScore(
        score=score,
        levels=levels,
        expected_count=len(expected),
        covered_count=covered,
        has_expectations=True,
    )
