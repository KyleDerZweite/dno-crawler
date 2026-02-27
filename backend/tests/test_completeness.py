"""
Tests for voltage level-based completeness scoring.
"""


from app.services.completeness import (
    compute_completeness,
    expected_voltage_levels,
)


class TestExpectedVoltageLevels:
    """Test derivation of expected voltage levels from MaStR data."""

    def test_ns_only(self) -> None:
        """Small DNO with only NS connection points."""
        result = expected_voltage_levels({"ns": 1000, "ms": 0, "hs": 0, "hoe": 0})
        assert result == ["NS"]

    def test_ns_and_ms(self) -> None:
        """Typical municipal utility: NS + MS."""
        result = expected_voltage_levels({"ns": 5000, "ms": 200, "hs": 0, "hoe": 0})
        assert result == ["MS", "MS/NS", "NS"]

    def test_full_dno(self) -> None:
        """Large DNO with all levels."""
        result = expected_voltage_levels({"ns": 50000, "ms": 5000, "hs": 500, "hoe": 0})
        assert result == ["HS", "HS/MS", "MS", "MS/NS", "NS"]

    def test_tso_with_hoe(self) -> None:
        """TSO-level operator."""
        result = expected_voltage_levels({"ns": 0, "ms": 0, "hs": 100, "hoe": 10})
        assert result == ["HöS", "HöS/HS", "HS", "HS/MS"]

    def test_all_zeros(self) -> None:
        """No connection points → no expected levels."""
        result = expected_voltage_levels({"ns": 0, "ms": 0, "hs": 0, "hoe": 0})
        assert result == []

    def test_none_values(self) -> None:
        """None values treated as 0."""
        result = expected_voltage_levels({"ns": None, "ms": 100, "hs": None, "hoe": None})
        assert result == ["MS", "MS/NS"]

    def test_missing_keys(self) -> None:
        """Missing keys treated as 0."""
        result = expected_voltage_levels({"ns": 500})
        assert result == ["NS"]

    def test_ordering_is_canonical(self) -> None:
        """Results always ordered highest to lowest voltage."""
        result = expected_voltage_levels({"ns": 1, "ms": 1, "hs": 1, "hoe": 1})
        assert result == ["HöS", "HöS/HS", "HS", "HS/MS", "MS", "MS/NS", "NS"]


class TestComputeCompleteness:
    """Test the overall completeness scoring."""

    def test_full_coverage(self) -> None:
        """DNO with all expected data → 100%."""
        cp = {"ns": 5000, "ms": 200, "hs": 0, "hoe": 0}
        netz_levels = {"NS", "MS/NS", "MS"}
        hlzf_levels = {"NS", "MS/NS", "MS"}

        result = compute_completeness(cp, netz_levels, hlzf_levels)

        assert result.score == 100
        assert result.expected_count == 3
        assert result.covered_count == 3
        assert result.has_expectations is True

    def test_partial_coverage(self) -> None:
        """DNO missing some levels → partial score."""
        cp = {"ns": 5000, "ms": 200, "hs": 0, "hoe": 0}
        netz_levels = {"NS"}  # Only NS, missing MS and MS/NS
        hlzf_levels = {"NS"}

        result = compute_completeness(cp, netz_levels, hlzf_levels)

        assert result.score == 33  # 1/3 = 33%
        assert result.expected_count == 3
        assert result.covered_count == 1
        assert result.has_expectations is True

    def test_no_coverage(self) -> None:
        """DNO with no data at all → 0%."""
        cp = {"ns": 5000, "ms": 200, "hs": 0, "hoe": 0}

        result = compute_completeness(cp, set(), set())

        assert result.score == 0
        assert result.expected_count == 3
        assert result.covered_count == 0

    def test_netzentgelte_without_hlzf_still_covered(self) -> None:
        """Coverage only requires netzentgelte, not hlzf."""
        cp = {"ns": 1000, "ms": 0, "hs": 0, "hoe": 0}
        netz_levels = {"NS"}
        hlzf_levels: set[str] = set()

        result = compute_completeness(cp, netz_levels, hlzf_levels)

        assert result.score == 100
        # Verify the level detail
        assert len(result.levels) == 1
        assert result.levels[0].has_netzentgelte is True
        assert result.levels[0].has_hlzf is False
        assert result.levels[0].covered is True

    def test_no_mastr_data_with_data(self) -> None:
        """No MaStR data but has extracted data → 100% (can't compute expectations)."""
        result = compute_completeness(None, {"NS"}, set())

        assert result.score == 100
        assert result.has_expectations is False

    def test_no_mastr_data_no_data(self) -> None:
        """No MaStR data and no extracted data → 0%."""
        result = compute_completeness(None, set(), set())

        assert result.score == 0
        assert result.has_expectations is False

    def test_zero_connection_points_with_data(self) -> None:
        """All connection points zero but data exists → 100%."""
        cp = {"ns": 0, "ms": 0, "hs": 0, "hoe": 0}
        result = compute_completeness(cp, {"NS"}, set())

        assert result.score == 100
        assert result.has_expectations is False

    def test_level_order_in_result(self) -> None:
        """Levels in result should be ordered highest to lowest."""
        cp = {"ns": 1, "ms": 1, "hs": 1, "hoe": 0}

        result = compute_completeness(cp, {"NS", "HS"}, set())

        level_names = [lvl.level for lvl in result.levels]
        assert level_names == ["HS", "HS/MS", "MS", "MS/NS", "NS"]

    def test_extra_data_beyond_expectations(self) -> None:
        """Data for levels not expected doesn't affect score."""
        cp = {"ns": 1000, "ms": 0, "hs": 0, "hoe": 0}
        # Has data for NS (expected) and HS (not expected)
        netz_levels = {"NS", "HS"}

        result = compute_completeness(cp, netz_levels, set())

        assert result.score == 100  # Only NS expected, and it's covered
        assert result.expected_count == 1
