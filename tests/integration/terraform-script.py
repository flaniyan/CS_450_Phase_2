import requests
import sys
import os

BASE_URL = "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/"
DEFAULT_UPLOAD_FILE = r"C:\Users\mdali\Downloads\hugging-face-model_1.0.0_full_1.0.0_full.zip"
UPLOAD_FILE_PATH = os.getenv("UPLOAD_TEST_FILE", DEFAULT_UPLOAD_FILE if os.path.exists(DEFAULT_UPLOAD_FILE) else None)

TEST_VALUES = {
    "id": "test-model",
    "name": "test-model",
    "artifact_type": "model",
    "version": "1.0.0"
}

def replace_placeholders(endpoint):
    """Replace {placeholder} with test values"""
    result = endpoint
    for placeholder, value in TEST_VALUES.items():
        result = result.replace(f"{{{placeholder}}}", value)
    return result

def test_endpoint(endpoint, method="GET", data=None, files=None):
    """Test an endpoint and return the result"""
    try:
        actual_endpoint = replace_placeholders(endpoint)
        url = f"{BASE_URL}{actual_endpoint}"
        print(f"\n[TEST] {method} {endpoint}")
        if actual_endpoint != endpoint:
            print(f"Resolved to: {actual_endpoint}")
        print(f"URL: {url}")
        
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            if files:
                r = requests.post(url, files=files, timeout=10)
            else:
                r = requests.post(url, json=data, timeout=10)
        elif method == "PUT":
            r = requests.put(url, json=data, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, timeout=10)
        elif method == "OPTIONS":
            r = requests.options(url, timeout=10)
        
        has_error = False
        try:
            response_json = r.json()
            if isinstance(response_json, dict) and "error" in response_json:
                has_error = True
            elif isinstance(response_json, list) and len(response_json) > 0:
                first_item = response_json[0]
                if isinstance(first_item, dict) and "error" in first_item:
                    has_error = True
        except:
            pass
        
        if r.status_code < 400 and not has_error:
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:200]}...")  # First 200 chars
        else:
            print(f"Response: {r.text[:200]}...")  # First 200 chars
        return r.status_code, r.text, has_error
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {e}")
        return None, str(e), True
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return None, str(e), True

print("Starting API Gateway Tests")
print("=" * 50)

# Test all endpoints
endpoints = [
    ("/health", "GET"),
    ("/health/components", "GET"),
    ("/admin", "GET"),
    ("/directory", "GET"),
    ("/artifact/model/{id}/rate", "GET"),
    ("/upload", "GET"),
    ("/upload", "POST"),
    ("/authenticate", "OPTIONS"),
    ("/artifacts", "POST"),
    ("/reset", "DELETE"),
    ("/artifact/ingest", "GET"),
    ("/artifact/ingest", "POST"),
    ("/artifact/model/{id}/lineage", "GET"),
    ("/artifact/model/{id}/license-check", "POST"),
    ("/artifact/{artifact_type}/{id}/cost", "GET"),
    ("/artifact/model/{id}/audit", "GET"),
    ("/artifact/model/{id}/download", "GET"),
    ("/artifact/byName/{name}", "GET"),
    ("/artifact/byRegEx", "POST"),
    ("/tracks", "GET"),
]

results = []
for endpoint, method in endpoints:
    data = None
    files = None
    if endpoint == "/artifact/byRegEx" and method == "POST":
        data = {"regex": ".*"}
    elif endpoint == "/artifacts" and method == "POST":
        data = {"metadata": {"name": "test-artifact", "type": "model"}, "data": {"url": "https://huggingface.co/test-model"}}
    elif endpoint == "/artifact/ingest" and method == "POST":
        data = {"name": "test-model", "version": "main"}
    elif endpoint == "/artifact/model/{id}/license-check" and method == "POST":
        data = {"github_url": "https://github.com/test/repo"}
    elif endpoint == "/upload" and method == "POST":
        if UPLOAD_FILE_PATH and os.path.exists(UPLOAD_FILE_PATH):
            with open(UPLOAD_FILE_PATH, 'rb') as f:
                file_content = f.read()
            files = {"file": (os.path.basename(UPLOAD_FILE_PATH), file_content, "application/zip")}
        else:
            import io
            import json
            zip_buffer = io.BytesIO()
            import zipfile
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                config_json = json.dumps({"model_type": "test", "vocab_size": 1000})
                zip_file.writestr("config.json", config_json)
                zip_file.writestr("test.txt", "test content")
            zip_buffer.seek(0)
            files = {"file": ("test.zip", zip_buffer, "application/zip")}
    status, response, has_error = test_endpoint(endpoint, method, data=data, files=files)
    results.append((endpoint, method, status, response, has_error))

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)

success_count = 0
for endpoint, method, status, response, has_error in results:
    if status and status < 400 and not has_error:
        print(f"[PASS] {method} {endpoint} - {status}")
        success_count += 1
    else:
        print(f"[FAIL] {method} {endpoint}")

print(f"\nSuccess Rate: {success_count}/{len(endpoints)} endpoints working")