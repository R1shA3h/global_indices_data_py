#!/usr/bin/env python3
"""
Test script for Groww Indices Scraper API
"""

import argparse
import json
import requests
import time
from urllib.parse import urljoin

def test_healthcheck(base_url):
    """Test the healthcheck endpoint"""
    endpoint = urljoin(base_url, "/api/healthcheck")
    
    start_time = time.time()
    response = requests.get(endpoint)
    end_time = time.time()
    
    print(f"\n🔍 Testing: {endpoint}")
    print(f"⏱️  Response time: {(end_time - start_time) * 1000:.2f}ms")
    print(f"🔢 Status code: {response.status_code}")
    
    try:
        data = response.json()
        print(f"📋 Response: {json.dumps(data, indent=2)}")
        return response.status_code == 200 and data.get("status") == "ok"
    except Exception as e:
        print(f"❌ Error parsing response: {e}")
        return False

def test_scrape(base_url, use_selenium=False, store_db=True, limit=10):
    """Test the scrape endpoint"""
    endpoint = urljoin(base_url, f"/api/scrape?selenium={str(use_selenium).lower()}&store_db={str(store_db).lower()}&limit={limit}")
    
    print(f"\n🔍 Testing: {endpoint}")
    print("⏱️  Scraping may take a while...")
    
    start_time = time.time()
    response = requests.get(endpoint)
    end_time = time.time()
    
    print(f"⏱️  Response time: {(end_time - start_time) * 1000:.2f}ms")
    print(f"🔢 Status code: {response.status_code}")
    
    try:
        data = response.json()
        
        # Print only first 3 indices for brevity
        if "indices" in data and len(data["indices"]) > 3:
            preview_data = {
                "message": data.get("message", ""),
                "count": data.get("count", 0),
                "indices": data["indices"][:3],
                "note": f"... {len(data['indices']) - 3} more indices not shown ..."
            }
            print(f"📋 Response (preview): {json.dumps(preview_data, indent=2)}")
        else:
            print(f"📋 Response: {json.dumps(data, indent=2)}")
            
        return response.status_code == 200 and "indices" in data and len(data["indices"]) > 0
    except Exception as e:
        print(f"❌ Error parsing response: {e}")
        return False

def run_tests(base_url, selenium=False):
    """Run all tests and report results"""
    print("=" * 60)
    print(f"🧪 TESTING GROWW INDICES SCRAPER API AT: {base_url}")
    print("=" * 60)
    
    tests = {
        "Healthcheck": test_healthcheck(base_url),
        "Basic Scrape": test_scrape(base_url, use_selenium=selenium, store_db=True, limit=10),
    }
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in tests.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        all_passed = all_passed and result
    
    print("\n" + "=" * 60)
    print(f"🏁 OVERALL: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the Groww Indices Scraper API")
    parser.add_argument("--url", default="http://localhost:5000", help="Base URL of the API (default: http://localhost:5000)")
    parser.add_argument("--selenium", action="store_true", help="Test with Selenium mode (may be slower)")
    
    args = parser.parse_args()
    run_tests(args.url, args.selenium) 