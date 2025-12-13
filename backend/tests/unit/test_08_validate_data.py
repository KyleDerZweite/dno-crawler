"""
Test 08: Validate Data

Tests the data validation step of the pipeline:
Extracted Data → Validation Logic → Valid/Invalid/Review Flag

Input: Hardcoded extracted data dictionaries
Action: Run validation logic
Goal: Assert valid data returns True, invalid data flags for review
Mock: None - tests validation rules
"""

import sys
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

# Valid HLZF record
VALID_HLZF_RECORD = {
    "voltage_level": "Niederspannung (NS)",
    "fruehling": "07:00 Uhr - 12:00 Uhr\n17:00 Uhr - 20:00 Uhr",
    "sommer": "10:00 Uhr - 14:00 Uhr",
    "herbst": "07:00 Uhr - 12:00 Uhr\n17:00 Uhr - 20:00 Uhr",
    "winter": "07:00 Uhr - 12:00 Uhr\n17:00 Uhr - 20:00 Uhr",
}

# Valid Netzentgelte record
VALID_NETZENTGELTE_RECORD = {
    "voltage_level": "NS-A",
    "leistungspreis": 45.50,
    "arbeitspreis": 5.20,
    "year": 2024,
    "source": "pdf",
}

# Invalid records (for testing validation)
INVALID_HLZF_RECORD_MISSING_FIELD = {
    "voltage_level": "NS",
    "fruehling": "07:00 - 12:00",
    # Missing other seasonal fields
}

INVALID_NETZENTGELTE_NEGATIVE_PRICE = {
    "voltage_level": "NS-A",
    "leistungspreis": -10.00,  # Invalid: negative price
    "arbeitspreis": 5.20,
}

SUSPICIOUS_NETZENTGELTE_HIGH_PRICE = {
    "voltage_level": "NS-A",
    "leistungspreis": 99999.99,  # Suspiciously high
    "arbeitspreis": 500.00,      # Also suspiciously high
}


# =============================================================================
# VALIDATION LOGIC
# =============================================================================

@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    confidence: float
    issues: list[str]
    requires_review: bool


def validate_hlzf_record(record: dict[str, Any]) -> ValidationResult:
    """
    Validate an HLZF record.
    
    Checks:
    - Required fields present (voltage_level + 4 seasonal fields)
    - Time format is reasonable
    - Voltage level is recognized
    """
    issues = []
    confidence = 1.0
    
    # Check required fields
    required = ["voltage_level", "fruehling", "sommer", "herbst", "winter"]
    for field in required:
        if field not in record or not record[field]:
            issues.append(f"Missing required field: {field}")
            confidence -= 0.2
    
    # Validate voltage level
    if "voltage_level" in record:
        vl = record["voltage_level"].upper()
        known_levels = ["NS", "MS", "HS", "HÖS", "NIEDERSPANNUNG", "MITTELSPANNUNG", "HOCHSPANNUNG"]
        if not any(level in vl for level in known_levels):
            issues.append(f"Unknown voltage level: {record['voltage_level']}")
            confidence -= 0.1
    
    # Validate time format (should contain "Uhr" or ":" patterns)
    for season in ["fruehling", "sommer", "herbst", "winter"]:
        if season in record and record[season]:
            time_str = record[season]
            if ":" not in time_str and "uhr" not in time_str.lower():
                issues.append(f"Invalid time format in {season}: {time_str}")
                confidence -= 0.1
    
    # Determine if review is needed
    requires_review = confidence < 0.8 or len(issues) > 0
    is_valid = confidence >= 0.5 and len([i for i in issues if "Missing required" in i]) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        confidence=max(0.0, confidence),
        issues=issues,
        requires_review=requires_review
    )


def validate_netzentgelte_record(record: dict[str, Any]) -> ValidationResult:
    """
    Validate a Netzentgelte record.
    
    Checks:
    - Required fields present (voltage_level, leistungspreis, arbeitspreis)
    - Prices are positive numbers
    - Prices are within reasonable ranges
    """
    issues = []
    confidence = 1.0
    
    # Check required fields
    required = ["voltage_level", "leistungspreis", "arbeitspreis"]
    for field in required:
        if field not in record or record[field] is None:
            issues.append(f"Missing required field: {field}")
            confidence -= 0.3
    
    # Validate prices are numbers
    for price_field in ["leistungspreis", "arbeitspreis"]:
        if price_field in record:
            try:
                price = float(record[price_field])
                
                # Check for negative prices
                if price < 0:
                    issues.append(f"Negative {price_field}: {price}")
                    confidence -= 0.3
                
                # Check for suspiciously high prices (flag for review)
                if price_field == "leistungspreis" and price > 500:
                    issues.append(f"Unusually high {price_field}: {price} (>500 €/kW)")
                    confidence -= 0.1
                elif price_field == "arbeitspreis" and price > 50:
                    issues.append(f"Unusually high {price_field}: {price} (>50 ct/kWh)")
                    confidence -= 0.1
                    
            except (ValueError, TypeError):
                issues.append(f"Invalid number format for {price_field}: {record[price_field]}")
                confidence -= 0.3
    
    # Validate voltage level format
    if "voltage_level" in record:
        vl = record["voltage_level"].upper()
        valid_prefixes = ["NS", "MS", "HS", "HÖS", "MS/NS", "HS/MS"]
        if not any(vl.startswith(prefix) for prefix in valid_prefixes):
            issues.append(f"Unknown voltage level: {record['voltage_level']}")
            confidence -= 0.1
    
    # Determine if review is needed
    requires_review = confidence < 0.9 or len(issues) > 0
    is_valid = confidence >= 0.7 and not any("Negative" in i for i in issues)
    
    return ValidationResult(
        is_valid=is_valid,
        confidence=max(0.0, confidence),
        issues=issues,
        requires_review=requires_review
    )


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_validate_data():
    """
    Test data validation logic with various inputs.
    """
    print(f"\n{'='*60}")
    print("TEST 08: Validate Data")
    print(f"{'='*60}")
    
    all_passed = True
    
    # Test 1: Valid HLZF record
    print("\n[Test 8a] Valid HLZF Record")
    print(f"  Input: {VALID_HLZF_RECORD}")
    
    result = validate_hlzf_record(VALID_HLZF_RECORD)
    
    if result.is_valid:
        print(f"  [PASS] Record is valid")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Requires Review: {result.requires_review}")
    else:
        print(f"  [FAIL] Expected valid, but got invalid")
        print(f"    Issues: {result.issues}")
        all_passed = False
    
    # Test 2: Valid Netzentgelte record
    print("\n[Test 8b] Valid Netzentgelte Record")
    print(f"  Input: {VALID_NETZENTGELTE_RECORD}")
    
    result = validate_netzentgelte_record(VALID_NETZENTGELTE_RECORD)
    
    if result.is_valid:
        print(f"  [PASS] Record is valid")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Requires Review: {result.requires_review}")
    else:
        print(f"  [FAIL] Expected valid, but got invalid")
        print(f"    Issues: {result.issues}")
        all_passed = False
    
    # Test 3: Invalid HLZF (missing fields)
    print("\n[Test 8c] Invalid HLZF Record (Missing Fields)")
    print(f"  Input: {INVALID_HLZF_RECORD_MISSING_FIELD}")
    
    result = validate_hlzf_record(INVALID_HLZF_RECORD_MISSING_FIELD)
    
    if result.requires_review:
        print(f"  [PASS] Record flagged for review")
        print(f"    Is Valid: {result.is_valid}")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Issues: {result.issues}")
    else:
        print(f"  [FAIL] Expected review flag, but not flagged")
        all_passed = False
    
    # Test 4: Invalid Netzentgelte (negative price)
    print("\n[Test 8d] Invalid Netzentgelte Record (Negative Price)")
    print(f"  Input: {INVALID_NETZENTGELTE_NEGATIVE_PRICE}")
    
    result = validate_netzentgelte_record(INVALID_NETZENTGELTE_NEGATIVE_PRICE)
    
    if not result.is_valid:
        print(f"  [PASS] Record correctly marked as invalid")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Issues: {result.issues}")
    else:
        print(f"  [FAIL] Expected invalid, but got valid")
        all_passed = False
    
    # Test 5: Suspicious data (high prices)
    print("\n[Test 8e] Suspicious Netzentgelte Record (High Prices)")
    print(f"  Input: {SUSPICIOUS_NETZENTGELTE_HIGH_PRICE}")
    
    result = validate_netzentgelte_record(SUSPICIOUS_NETZENTGELTE_HIGH_PRICE)
    
    if result.requires_review:
        print(f"  [PASS] Record flagged for review")
        print(f"    Is Valid: {result.is_valid}")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Issues: {result.issues}")
    else:
        print(f"  [FAIL] Expected review flag for suspicious data")
        all_passed = False
    
    return all_passed


def test_edge_cases():
    """
    Test edge cases for validation.
    """
    print(f"\n{'='*60}")
    print("TEST 08b: Validation Edge Cases")
    print(f"{'='*60}")
    
    all_passed = True
    
    # Test empty record
    print("\n[Test] Empty Record")
    result = validate_hlzf_record({})
    
    if not result.is_valid and result.requires_review:
        print(f"  [PASS] Empty record handled correctly")
        print(f"    Issues: {result.issues}")
    else:
        print(f"  [FAIL] Empty record not handled correctly")
        all_passed = False
    
    # Test with None values
    print("\n[Test] Record with None values")
    result = validate_netzentgelte_record({
        "voltage_level": "NS",
        "leistungspreis": None,
        "arbeitspreis": 5.0
    })
    
    if result.requires_review:
        print(f"  [PASS] None values flagged for review")
        print(f"    Issues: {result.issues}")
    else:
        print(f"  [FAIL] None values not handled correctly")
        all_passed = False
    
    return all_passed


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Running Data Validation Tests")
        print("="*60)
        
        success1 = test_validate_data()
        success2 = test_edge_cases()
        
        overall_success = success1 and success2
        
        print(f"\n{'='*60}")
        print("TEST RESULTS:")
        print(f"  - Validation Tests: {'✅ PASSED' if success1 else '❌ FAILED'}")
        print(f"  - Edge Cases:       {'✅ PASSED' if success2 else '❌ FAILED'}")
        print("-" * 60)
        if overall_success:
            print("RESULT: ✅ ALL TESTS PASSED")
        else:
            print("RESULT: ❌ SOME TESTS FAILED")
        print(f"{'='*60}\n")
        sys.exit(0 if overall_success else 1)
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
