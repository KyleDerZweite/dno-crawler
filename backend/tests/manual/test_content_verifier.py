#!/usr/bin/env python3
"""
Manual test for ContentVerifier.

Tests the content verification logic against sample text/patterns
to ensure netzentgelte vs hlzf discrimination works correctly.
"""

import asyncio
import sys
sys.path.insert(0, '/home/kyle/CodingProjects/dno-crawler/backend')

from app.services.content_verifier import ContentVerifier, score_for_data_type


def test_text_verification():
    """Test text-based verification."""
    verifier = ContentVerifier()
    
    # Sample Netzentgelte text
    netzentgelte_text = """
    Preisblatt Netzentgelte Strom 2024
    
    Netznutzungsentgelte gemäß § 17 StromNEV
    
    Netzebene                    Leistungspreis    Arbeitspreis
                                 €/kW/a            ct/kWh
    Hochspannungsnetz           12,50              2,34
    Mittelspannungsnetz         25,80              3,67
    Niederspannungsnetz         45,20              5,89
    """
    
    # Sample HLZF text
    hlzf_text = """
    Hochlastzeitfenster gemäß § 19 StromNEV
    
    HLZF-Tabelle für das Jahr 2024
    
    Netzebene              Winter          Sommer          Frühling/Herbst
    Hochspannung           08:00-20:00     entfällt        09:00-18:00
    Mittelspannung         07:00-21:00     entfällt        08:00-19:00
    """
    
    # Mixed/ambiguous text
    mixed_text = """
    Dokumente zum Netzzugang
    
    Downloads:
    - Preisblatt 2024
    - Netzentgelte Strom
    """
    
    print("=" * 60)
    print("Testing ContentVerifier text verification")
    print("=" * 60)
    
    # Test 1: Netzentgelte text with netzentgelte expected
    result = verifier.verify_text(netzentgelte_text, "netzentgelte", 2024)
    print(f"\n[Test 1] Netzentgelte text → expecting 'netzentgelte'")
    print(f"  Verified: {result.is_verified}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Detected: {result.detected_data_type}")
    print(f"  Keywords found: {result.keywords_found[:5]}")
    assert result.is_verified, "Should verify as netzentgelte"
    assert result.confidence >= 0.5, "Should have high confidence"
    print("  ✅ PASSED")
    
    # Test 2: Netzentgelte text with HLZF expected (should fail)
    result = verifier.verify_text(netzentgelte_text, "hlzf", 2024)
    print(f"\n[Test 2] Netzentgelte text → expecting 'hlzf'")
    print(f"  Verified: {result.is_verified}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Detected: {result.detected_data_type}")
    assert not result.is_verified, "Should NOT verify as hlzf"
    print("  ✅ PASSED (correctly rejected)")
    
    # Test 3: HLZF text with HLZF expected
    result = verifier.verify_text(hlzf_text, "hlzf", 2024)
    print(f"\n[Test 3] HLZF text → expecting 'hlzf'")
    print(f"  Verified: {result.is_verified}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Detected: {result.detected_data_type}")
    print(f"  Keywords found: {result.keywords_found[:5]}")
    assert result.is_verified, "Should verify as hlzf"
    assert result.confidence >= 0.5, "Should have high confidence"
    print("  ✅ PASSED")
    
    # Test 4: HLZF text with Netzentgelte expected (should fail)
    result = verifier.verify_text(hlzf_text, "netzentgelte", 2024)
    print(f"\n[Test 4] HLZF text → expecting 'netzentgelte'")
    print(f"  Verified: {result.is_verified}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Detected: {result.detected_data_type}")
    assert not result.is_verified, "Should NOT verify as netzentgelte"
    print("  ✅ PASSED (correctly rejected)")
    
    print("\n" + "=" * 60)
    print("All text verification tests passed!")
    print("=" * 60)


def test_url_scoring():
    """Test URL-based scoring."""
    print("\n" + "=" * 60)
    print("Testing URL scoring for data type")
    print("=" * 60)
    
    test_cases = [
        # (url, data_type, expected_positive)
        ("https://dno.de/downloads/netzentgelte-2024.pdf", "netzentgelte", True),
        ("https://dno.de/downloads/netzentgelte-2024.pdf", "hlzf", False),
        ("https://dno.de/downloads/preisblatt-strom-2024.pdf", "netzentgelte", True),
        ("https://dno.de/downloads/hlzf-2024.pdf", "hlzf", True),
        ("https://dno.de/downloads/hochlastzeitfenster-2024.pdf", "hlzf", True),
        ("https://dno.de/downloads/hochlastzeitfenster-2024.pdf", "netzentgelte", False),
        ("https://dno.de/downloads/regelungen-2024.pdf", "hlzf", True),
    ]
    
    for url, data_type, expected_positive in test_cases:
        score = score_for_data_type(url, data_type)
        is_positive = score > 0
        status = "✅" if is_positive == expected_positive else "❌"
        print(f"{status} {url[-40:]:40} | {data_type:12} | score: {score:+6.1f}")
        
        if is_positive != expected_positive:
            print(f"   ⚠️  Expected {'positive' if expected_positive else 'negative'} score")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_text_verification()
    test_url_scoring()
    print("\n🎉 All tests completed!")
