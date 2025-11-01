import requests
import sys
import os
import json

BASE_URL = "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/"
DEFAULT_UPLOAD_FILE = r"C:\Users\mdali\Downloads\hugging-face-model_1.0.0_full_1.0.0_full.zip"

def upload_test_model():
    """Upload a test model using DEFAULT_UPLOAD_FILE via /artifact/model/{id}/upload"""
    if not os.path.exists(DEFAULT_UPLOAD_FILE):
        print(f"Upload file not found: {DEFAULT_UPLOAD_FILE}")
        return None
    try:
        filename = os.path.basename(DEFAULT_UPLOAD_FILE).replace('.zip', '').replace('_', '-')
        model_id = filename.split('-')[0] if '-' in filename else filename[:20]
        url = f"{BASE_URL}artifact/model/{model_id}/upload"
        with open(DEFAULT_UPLOAD_FILE, 'rb') as f:
            file_content = f.read()
        files = {"file": (os.path.basename(DEFAULT_UPLOAD_FILE), file_content, "application/zip")}
        print(f"Uploading {DEFAULT_UPLOAD_FILE} to /artifact/model/{model_id}/upload...")
        r = requests.post(url, files=files, timeout=30)
        print(f"Upload response status: {r.status_code}")
        print(f"Upload response: {r.text}")
        if r.status_code == 200:
            data = r.json()
            returned_model_id = data.get("model_id") or model_id
            version = data.get("version", "1.0.0")
            return returned_model_id, version
        else:
            print(f"Upload failed with status {r.status_code}: {r.text}")
        return None
    except Exception as e:
        print(f"Failed to upload test model: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_real_models():
    """Fetch real models from S3 via API, or upload one if none exist"""
    try:
        url = f"{BASE_URL}artifact/directory"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            models = data.get("artifacts", [])
            if models:
                model = models[0]
                model_name = model.get("name")
                model_version = model.get("version")
                if model_name and model_version:
                    return model_name, model_version
        print("No models found in directory, uploading a test model...")
        uploaded = upload_test_model()
        if uploaded:
            model_id, version = uploaded
            if model_id and version:
                print(f"Successfully uploaded test model: {model_id} v{version}")
                return model_id, version
        print("ERROR: Failed to get or upload a real model. Cannot proceed without real S3 resources.")
        return None, None
    except Exception as e:
        print(f"Failed to fetch real models: {e}")
        return None, None

def test_endpoint(endpoint, method="GET", data=None, files=None):
    """Test an endpoint and return the result"""
    try:
        if BASE_URL.endswith("/") and endpoint.startswith("/"):
            url = f"{BASE_URL.rstrip('/')}{endpoint}"
        elif not BASE_URL.endswith("/") and not endpoint.startswith("/"):
            url = f"{BASE_URL}/{endpoint}"
        else:
            url = f"{BASE_URL}{endpoint}"
        print(f"\n[TEST] {method} {endpoint}")
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

real_model_id, real_version = get_real_models()
if not real_model_id or not real_version:
    print("ERROR: Cannot proceed without real S3 resources. Exiting.")
    sys.exit(1)

print(f"Using real model ID: {real_model_id}, version: {real_version}")
artifact_type = "model"
model_name = real_model_id

# Debug: Print the endpoints to verify f-strings are evaluated
print(f"DEBUG: real_model_id = {real_model_id!r}")
print(f"DEBUG: Testing endpoint will be: /artifact/model/{real_model_id}/upload")

# Test all endpoints from index.py with real values
endpoints = [
    ("/", "GET"),
    ("/health", "GET"),
    ("/health/components", "GET"),
    ("/authenticate", "PUT"),
    ("/artifacts", "POST"),
    ("/reset", "DELETE"),
    ("/artifact", "GET"),
    (f"/artifact/{artifact_type}", "GET"),
    (f"/artifact/{artifact_type}", "POST"),
    (f"/artifact/{artifact_type}/{real_model_id}", "GET"),
    (f"/artifact/byName/{model_name}", "GET"),
    ("/artifact/byRegEx", "POST"),
    (f"/artifact/{artifact_type}/{real_model_id}", "PUT"),
    (f"/artifact/{artifact_type}/{real_model_id}", "DELETE"),
    (f"/artifact/{artifact_type}/{real_model_id}/cost", "GET"),
    (f"/artifact/{artifact_type}/{real_model_id}/audit", "GET"),
    (f"/artifact/model/{real_model_id}/rate", "GET"),
    (f"/artifact/model/{real_model_id}/lineage", "GET"),
    (f"/artifact/model/{real_model_id}/license-check", "POST"),
    ("/upload", "POST"),
    (f"/artifact/model/{real_model_id}/upload", "POST"),
    (f"/artifact/model/{real_model_id}/download", "GET"),
    ("/artifact/ingest", "GET"),
    ("/artifact/ingest", "POST"),
    ("/artifact/directory", "GET"),
    ("/admin", "GET"),
]

results = []
for endpoint, method in endpoints:
    data = None
    files = None
    if endpoint == "/artifact/byRegEx" and method == "POST":
        data = {"regex": ".*"}
    elif endpoint == "/artifacts" and method == "POST":
        data = {"metadata": {"name": real_model_id, "type": "model"}, "data": {"name": real_model_id}}
    elif f"/artifact/{artifact_type}" == endpoint and method == "POST":
        data = {"url": f"https://example.com/{real_model_id}", "version": real_version}
    elif f"/artifact/{artifact_type}/{real_model_id}" == endpoint and method == "PUT":
        data = {"metadata": {"name": real_model_id}, "data": {"version": real_version}}
    elif endpoint == "/authenticate" and method == "PUT":
        data = {"user": {"name": "ece30861defaultadminuser", "is_admin": True}, "secret": {"password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"}}
    elif endpoint == "/artifact/ingest" and method == "POST":
        data = {"name": real_model_id, "version": real_version}
    elif endpoint == "/upload" and method == "POST":
        if os.path.exists(DEFAULT_UPLOAD_FILE):
            with open(DEFAULT_UPLOAD_FILE, 'rb') as f:
                file_content = f.read()
            files = {"file": (os.path.basename(DEFAULT_UPLOAD_FILE), file_content, "application/zip")}
    elif endpoint == f"/artifact/model/{real_model_id}/upload" and method == "POST":
        if os.path.exists(DEFAULT_UPLOAD_FILE):
            with open(DEFAULT_UPLOAD_FILE, 'rb') as f:
                file_content = f.read()
            files = {"file": (os.path.basename(DEFAULT_UPLOAD_FILE), file_content, "application/zip")}
    elif f"/artifact/model/{real_model_id}/license-check" == endpoint and method == "POST":
        data = {"github_url": "https://github.com/test/repo"}
    status, response = test_endpoint(endpoint, method, data=data, files=files)
    results.append((endpoint, method, status, response))

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)

success_count = 0
for endpoint, method, status, response in results:
    if status and 200 <= status < 300:
        print(f"[PASS] {method} {endpoint} - {status}")
        success_count += 1
    else:
        print(f"[FAIL] {method} {endpoint} - {status if status else 'No response'}")

print(f"\nSuccess Rate: {success_count}/{len(endpoints)} endpoints successful")