"""Shared extraction validation helpers used by extract and validate steps."""


def is_valid_data_value(value: object) -> bool:
    """Return True when a value should count as present data."""
    if value is None:
        return False
    value_str = str(value).strip().lower()
    return value_str not in {"-", "n/a", "null", "none", "", "entfällt", "keine"}


def validate_extraction_sanity(records: list[dict], data_type: str) -> tuple[bool, str]:
    """Run shared minimum sanity checks before persistence."""
    if data_type == "netzentgelte":
        if len(records) < 2:
            return False, f"Too few records: {len(records)} (minimum 2 required)"

        valid_records = 0
        for record in records:
            if any(
                is_valid_data_value(record.get(field))
                for field in ("leistung", "arbeit", "leistung_unter_2500h", "arbeit_unter_2500h")
            ):
                valid_records += 1

        if valid_records < 2:
            return False, (
                f"Too few valid records with prices: {valid_records} (minimum 2 required)"
            )

        return True, "OK"

    if len(records) < 2:
        return (
            False,
            f"Missing voltage levels: only {len(records)} extracted (minimum 2 required)",
        )

    return True, "OK"
