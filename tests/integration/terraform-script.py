import requests
import sys

BASE_URL = "https://dyrelddhj1.execute-api.us-east-1.amazonaws.com/prod"

def test_endpoint(endpoint, method="GET"):
    """Test an endpoint and return the result"""
    try:
        url = f"{BASE_URL}{endpoint}"
        print(f"\n[TEST] {method} {endpoint}")
        print(f"URL: {url}")
        
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            r = requests.post(url, timeout=10)
        elif method == "PUT":
            r = requests.put(url, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, timeout=10)
        elif method == "OPTIONS":
            r = requests.options(url, timeout=10)
        
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:200]}...")  # First 200 chars
        return r.status_code, r.text
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {e}")
        return None, str(e)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return None, str(e)

print("Starting API Gateway Tests")
print("=" * 50)

# Test all endpoints
endpoints = [
    ("/health", "GET"),
    ("/health/components", "GET"),
    ("/admin", "GET"),
    ("/directory", "GET"),
    ("/rate", "GET"),
    ("/upload", "GET"),
    ("/upload", "POST"),
    ("/authenticate", "PUT"),
    ("/artifacts", "POST"),
    ("/reset", "DELETE"),
]

results = []
for endpoint, method in endpoints:
    status, response = test_endpoint(endpoint, method)
    results.append((endpoint, method, status, response))

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)

success_count = 0
for endpoint, method, status, response in results:
    if status and status < 400:
        print(f"[PASS] {method} {endpoint} - {status}")
        success_count += 1
    else:
        print(f"[FAIL] {method} {endpoint} - {status}")

print(f"\nSuccess Rate: {success_count}/{len(endpoints)} endpoints working")