"""
Manual test script for VNB Digital DNO details extraction.

Tests the get_vnb_details() method that fetches DNO homepage URL and contact
information via GraphQL for BFS crawl seeding.

Run:
    python -m tests.manual.vnb_details_test
"""

import asyncio

from app.services.vnb_digital import VNBDigitalClient

# =============================================================================
# Test Cases
# =============================================================================

TEST_DNOS = [
    {
        "vnb_id": "7399",
        "expected_name": "RheinNetz GmbH",
        "expected_homepage": "https://www.rheinnetz.de/",
    },
    {
        "vnb_id": "7332",
        "expected_name": "Westnetz",
        "expected_homepage": "https://www.westnetz.de/",
    },
]


# =============================================================================
# Tests
# =============================================================================

async def test_get_vnb_details():
    """Test get_vnb_details for multiple DNOs."""
    print("\n" + "=" * 60)
    print("🔍 GET VNB DETAILS TEST")
    print("=" * 60)

    client = VNBDigitalClient(request_delay=1.0)
    passed = 0

    for test in TEST_DNOS:
        vnb_id = test["vnb_id"]
        print(f"\n📍 Testing VNB ID: {vnb_id}")

        details = await client.get_vnb_details(vnb_id)

        if details is None:
            print("   ❌ FAILED: Could not fetch details")
            continue

        print(f"   Name: {details.name}")
        print(f"   Homepage: {details.homepage_url}")
        print(f"   Phone: {details.phone}")
        print(f"   Email: {details.email}")
        print(f"   Address: {details.address}")

        # Validate
        name_ok = test["expected_name"].lower() in details.name.lower()
        homepage_ok = details.homepage_url and test["expected_homepage"].rstrip("/") in details.homepage_url.rstrip("/")

        if name_ok and homepage_ok:
            print("   ✅ PASSED")
            passed += 1
        else:
            print("   ❌ FAILED validation")
            if not name_ok:
                print(f"      Expected name containing: {test['expected_name']}")
            if not homepage_ok:
                print(f"      Expected homepage: {test['expected_homepage']}")

    print(f"\n   Result: {passed}/{len(TEST_DNOS)} passed")
    return passed == len(TEST_DNOS)


async def test_full_flow():
    """Test full flow: Address → VNB → Details → Homepage."""
    print("\n" + "=" * 60)
    print("🔗 FULL FLOW TEST: Address → VNB → Details → Homepage")
    print("=" * 60)

    client = VNBDigitalClient(request_delay=1.0)

    test_address = "Parkgürtel 24, 50823 Köln"
    print(f"\n📍 Test Address: {test_address}")

    # Step 1: Get location from address
    location = await client.search_address(test_address)
    if not location:
        print("   ❌ FAILED: Could not resolve address")
        return False
    print(f"   ✅ Location: {location.title}")
    print(f"   📍 Coordinates: {location.coordinates}")

    # Step 2: Get VNB from coordinates
    vnbs = await client.lookup_by_coordinates(location.coordinates)
    if not vnbs:
        print("   ❌ FAILED: No VNBs found")
        return False

    vnb = vnbs[0]
    print(f"   ✅ VNB Found: {vnb.name} (ID: {vnb.vnb_id})")

    # Step 3: Get extended details
    details = await client.get_vnb_details(vnb.vnb_id)
    if not details:
        print("   ❌ FAILED: Could not fetch VNB details")
        return False

    print(f"   ✅ Homepage: {details.homepage_url}")
    print(f"   ✅ Phone: {details.phone}")
    print(f"   ✅ Email: {details.email}")

    # Verify we got a usable homepage for BFS crawling
    if details.homepage_url and details.homepage_url.startswith("http"):
        print("\n   🎉 SUCCESS: Got homepage URL for BFS crawl seed!")
        return True
    else:
        print("\n   ❌ FAILED: No valid homepage URL extracted")
        return False


# =============================================================================
# Main
# =============================================================================

async def main():
    print("=" * 60)
    print("🏢 VNB DIGITAL CLIENT TEST (Async-Only)")
    print("=" * 60)

    results = {}

    # Run tests
    results["get_vnb_details"] = await test_get_vnb_details()
    results["full_flow"] = await test_full_flow()

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {test_name}")

    all_passed = all(results.values())
    print("\n" + ("✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"))

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
