import requests
import sys
import os
import json
from pathlib import Path
from urllib.parse import quote

BASE_URL = os.getenv("API_GATEWAY_URL", "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/")
DEFAULT_UPLOAD_FILE = os.getenv("UPLOAD_FILE_PATH", r"C:\Users\mdali\Downloads\manual-upload-model_1.0.0_full.zip")
DEFAULT_TEST_MODEL = os.getenv("TEST_MODEL_ID", "maya-research/maya1")
AUTH_JSON_PATH = os.getenv("AUTH_JSON_PATH", "auth.json")

def load_auth_json():
    """Load authentication credentials from auth.json"""
    auth_path = Path(AUTH_JSON_PATH)
    if not auth_path.exists():
        # Try relative to script directory
        script_dir = Path(__file__).parent.parent.parent
        auth_path = script_dir / "auth.json"
        if not auth_path.exists():
            raise FileNotFoundError(f"auth.json not found at {AUTH_JSON_PATH} or {auth_path}")
    
    with open(auth_path, 'r') as f:
        return json.load(f)

def get_auth_token():
    """Authenticate using auth.json and return the token"""
    try:
        auth_data = load_auth_json()
        url = f"{BASE_URL}authenticate"
        if BASE_URL.endswith("/"):
            url = f"{BASE_URL.rstrip('/')}/authenticate"
        
        print(f"Authenticating using auth.json...")
        r = requests.put(url, json=auth_data, timeout=10)
        
        if r.status_code == 200:
            # Token is returned as a plain string (not JSON)
            token = r.text.strip().strip('"')
            if token.startswith("bearer "):
                token = token[7:]  # Remove "bearer " prefix if present
            print(f"Authentication successful")
            return token
        else:
            print(f"Authentication failed with status {r.status_code}: {r.text}")
            return None
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return None
    except Exception as e:
        print(f"Failed to authenticate: {e}")
        import traceback
        traceback.print_exc()
        return None

def upload_test_model(token=None):
    """Upload a test model using DEFAULT_UPLOAD_FILE via /artifact/model/{id}/upload"""
    if not DEFAULT_UPLOAD_FILE or not os.path.exists(DEFAULT_UPLOAD_FILE):
        if DEFAULT_UPLOAD_FILE:
            print(f"Upload file not found: {DEFAULT_UPLOAD_FILE}")
        return None
    try:
        filename = os.path.basename(DEFAULT_UPLOAD_FILE).replace('.zip', '').replace('_', '-')
        model_id = filename.split('-')[0] if '-' in filename else filename[:20]
        url = f"{BASE_URL}artifact/model/{model_id}/upload"
        with open(DEFAULT_UPLOAD_FILE, 'rb') as f:
            file_content = f.read()
        files = {"file": (os.path.basename(DEFAULT_UPLOAD_FILE), file_content, "application/zip")}
        
        headers = {}
        if token:
            headers["X-Authorization"] = f"bearer {token}"
            headers["Authorization"] = f"Bearer {token}"
        
        print(f"Uploading {DEFAULT_UPLOAD_FILE} to /artifact/model/{model_id}/upload...")
        r = requests.post(url, files=files, headers=headers, timeout=30)
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

def ingest_test_model(token=None):
    """Ingest a test model from HuggingFace"""
    try:
        model_id = os.getenv("INGEST_MODEL_ID", DEFAULT_TEST_MODEL)
        version = os.getenv("INGEST_MODEL_VERSION", "main")
        url = f"{BASE_URL}artifact/ingest"
        
        headers = {}
        if token:
            headers["X-Authorization"] = f"bearer {token}"
            headers["Authorization"] = f"Bearer {token}"
        
        # Try form data first (as the endpoint checks form data first)
        data = {"name": model_id, "version": version}
        
        print(f"Ingesting model {model_id} v{version} from HuggingFace...")
        r = requests.post(url, data=data, headers=headers, timeout=300)
        print(f"Ingest response status: {r.status_code}")
        if r.status_code == 200:
            try:
                response_data = r.json()
                if isinstance(response_data, list) and len(response_data) > 0 and "error" in response_data[0]:
                    print(f"Ingest failed: {response_data[0].get('error')}")
                    return None
                elif isinstance(response_data, dict) and "error" in response_data:
                    print(f"Ingest failed: {response_data.get('error')}")
                    return None
                print(f"Ingest response: {r.text[:200]}...")
                
                # Extract the actual artifact ID from the response
                artifact_id = None
                if isinstance(response_data, dict):
                    # Check for 'id' in details or at top level
                    if "details" in response_data and "id" in response_data["details"]:
                        artifact_id = str(response_data["details"]["id"])
                    elif "id" in response_data:
                        artifact_id = str(response_data["id"])
                
                # Fallback to cleaned model name if no ID found
                if not artifact_id:
                    clean_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").replace("/", "-")
                    artifact_id = clean_model_id
                
                return artifact_id, version
            except:
                print(f"Ingest response (non-JSON): {r.text[:200]}...")
                # Fallback to cleaned model name
                clean_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").replace("/", "-")
                return clean_model_id, version
        else:
            print(f"Ingest failed with status {r.status_code}: {r.text[:200]}...")
        return None
    except Exception as e:
        print(f"Failed to ingest test model: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_real_models(token=None):
    """Fetch real models from S3 via API, or ingest/upload one if none exist"""
    try:
        url = f"{BASE_URL}artifact/directory"
        headers = {}
        if token:
            headers["X-Authorization"] = f"bearer {token}"
            headers["Authorization"] = f"Bearer {token}"
        
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            models = data.get("artifacts", [])
            if models:
                model = models[0]
                model_name = model.get("name")
                model_version = model.get("version")
                if model_name and model_version:
                    return model_name, model_version
        print("No models found in directory, trying to ingest or upload a test model...")
        ingested = ingest_test_model(token)
        if ingested:
            model_id, version = ingested
            if model_id and version:
                print(f"Successfully ingested test model: {model_id} v{version}")
                return model_id, version
        print("Ingest failed or no model specified, trying upload from file...")
        uploaded = upload_test_model(token)
        if uploaded:
            model_id, version = uploaded
            if model_id and version:
                print(f"Successfully uploaded test model: {model_id} v{version}")
                return model_id, version
        print("ERROR: Failed to get, ingest, or upload a real model. Cannot proceed without real S3 resources.")
        print("Set INGEST_MODEL_ID environment variable (e.g., 'maya-research/maya1') or UPLOAD_FILE_PATH, or ensure models exist in S3.")
        return None, None
    except Exception as e:
        print(f"Failed to fetch real models: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_endpoint(endpoint, method="GET", data=None, files=None, token=None):
    """Test an endpoint and return the result"""
    try:
        # URL encode the endpoint to handle special characters like "/" in model names
        # But preserve the path structure (only encode the actual parameter values)
        if "/byName/" in endpoint:
            # Split the endpoint to preserve path structure but encode the name parameter
            parts = endpoint.split("/byName/")
            if len(parts) == 2:
                encoded_name = quote(parts[1], safe="")
                endpoint = f"{parts[0]}/byName/{encoded_name}"
        
        if BASE_URL.endswith("/") and endpoint.startswith("/"):
            url = f"{BASE_URL.rstrip('/')}{endpoint}"
        elif not BASE_URL.endswith("/") and not endpoint.startswith("/"):
            url = f"{BASE_URL}/{endpoint}"
        else:
            url = f"{BASE_URL}{endpoint}"
        print(f"\n[TEST] {method} {endpoint}")
        print(f"URL: {url}")
        
        # Prepare headers
        headers = {}
        if token:
            headers["X-Authorization"] = f"bearer {token}"
            headers["Authorization"] = f"Bearer {token}"
        
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            if files:
                r = requests.post(url, files=files, headers=headers, timeout=10)
            else:
                r = requests.post(url, json=data, headers=headers, timeout=10)
        elif method == "PUT":
            r = requests.put(url, json=data, headers=headers, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=10)
        elif method == "OPTIONS":
            r = requests.options(url, headers=headers, timeout=10)
        
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

# Authenticate and get token using auth.json
auth_token = get_auth_token()
if not auth_token:
    print("WARNING: Failed to get authentication token. Some endpoints may fail.")
else:
    print(f"Authentication token obtained (length: {len(auth_token)})")

real_model_id, real_version = get_real_models(token=auth_token)
if not real_model_id or not real_version:
    print("ERROR: Cannot proceed without real S3 resources. Exiting.")
    sys.exit(1)

print(f"Using real model ID: {real_model_id}, version: {real_version}")
artifact_type = "model"

# For byName endpoint, we need the model name, not the ID
# Try to get the name from the artifact metadata
model_name = real_model_id  # Default to ID, will try to get name from GET endpoint
try:
    # Try to get artifact metadata to find the name
    test_url = f"{BASE_URL}artifacts/{artifact_type}/{real_model_id}"
    if BASE_URL.endswith("/") and test_url.startswith("/"):
        test_url = f"{BASE_URL.rstrip('/')}/artifacts/{artifact_type}/{real_model_id}"
    elif not BASE_URL.endswith("/") and not test_url.startswith("/"):
        test_url = f"{BASE_URL}/artifacts/{artifact_type}/{real_model_id}"
    else:
        test_url = f"{BASE_URL}artifacts/{artifact_type}/{real_model_id}"
    
    headers = {}
    if auth_token:
        headers["X-Authorization"] = f"bearer {auth_token}"
    r = requests.get(test_url, headers=headers, timeout=10)
    if r.status_code == 200:
        data = r.json()
        if "metadata" in data and "name" in data["metadata"]:
            model_name = data["metadata"]["name"]
            print(f"Found model name: {model_name}")
except Exception as e:
    print(f"Could not fetch model name, using ID: {e}")
    model_name = real_model_id

# Debug: Print the endpoints to verify f-strings are evaluated
print(f"DEBUG: real_model_id = {real_model_id!r}")
print(f"DEBUG: Testing endpoints from OpenAPI spec with model_id: {real_model_id}")

# Test all endpoints from OpenAPI spec (ece461_fall_2025_openapi_spec (2).yaml)
# Only endpoints defined in the spec are included
# Order: Test endpoints that require artifact existence BEFORE DELETE
endpoints = [
    # Public endpoints (no auth required)
    ("/health", "GET"),
    ("/health/components", "GET"),
    ("/authenticate", "PUT"),
    ("/tracks", "GET"),
    
    # Authenticated endpoints that need artifact to exist (test BEFORE DELETE)
    ("/artifacts", "POST"),
    (f"/artifacts/{artifact_type}/{real_model_id}", "GET"),
    (f"/artifacts/{artifact_type}/{real_model_id}", "PUT"),
    (f"/artifact/{artifact_type}/{real_model_id}/cost", "GET"),
    (f"/artifact/{artifact_type}/{real_model_id}/audit", "GET"),
    (f"/artifact/model/{real_model_id}/rate", "GET"),
    (f"/artifact/model/{real_model_id}/lineage", "GET"),
    (f"/artifact/model/{real_model_id}/license-check", "POST"),
    (f"/artifact/byName/{model_name}", "GET"),
    ("/artifact/byRegEx", "POST"),
    
    # Endpoints that create/modify artifacts (test before DELETE)
    (f"/artifact/{artifact_type}", "POST"),
    
    # DELETE operations (test LAST, after all other operations)
    (f"/artifacts/{artifact_type}/{real_model_id}", "DELETE"),
    ("/reset", "DELETE"),
]

results = []
for endpoint, method in endpoints:
    data = None
    files = None
    if endpoint == "/artifact/byRegEx" and method == "POST":
        data = {"regex": ".*"}
    elif endpoint == "/artifacts" and method == "POST":
        # POST /artifacts - requires array of ArtifactQuery per spec
        # ArtifactQuery requires: name (required), types (optional array)
        data = [{"name": "*", "types": ["model"]}]  # Use "*" to enumerate all
    elif f"/artifacts/{artifact_type}/{real_model_id}" == endpoint and method == "PUT":
        # PUT /artifacts/{artifact_type}/{id} - requires Artifact schema per spec
        data = {
            "metadata": {"name": real_model_id, "id": real_model_id, "type": artifact_type},
            "data": {"url": f"https://huggingface.co/{real_model_id}"}
        }
    elif endpoint == "/authenticate" and method == "PUT":
        # Use auth.json for authentication
        try:
            data = load_auth_json()
        except Exception as e:
            print(f"Warning: Could not load auth.json: {e}")
            data = None
    elif f"/artifact/{artifact_type}" == endpoint and method == "POST":
        # POST /artifact/{artifact_type} - requires url in request body per spec
        # Use a different model name to avoid conflicts (this creates a new artifact)
        # Use a simple test model that exists on HuggingFace
        test_model_name = "gpt2"  # Simple model that should exist
        data = {"url": f"https://huggingface.co/{test_model_name}"}
    elif f"/artifact/model/{real_model_id}/license-check" == endpoint and method == "POST":
        # POST /artifact/model/{id}/license-check - requires github_url per spec
        data = {"github_url": "https://github.com/test/repo"}
    
    # Determine if endpoint requires authentication based on OpenAPI spec
    # Public endpoints that don't need auth (from spec)
    public_endpoints = ["/health", "/health/components", "/authenticate", "/tracks"]
    requires_auth = not any(endpoint == public or endpoint.startswith(public + "/") for public in public_endpoints)
    
    # Use token for authenticated endpoints (all endpoints except public ones require X-Authorization per spec)
    token_to_use = auth_token if requires_auth else None
    status, response = test_endpoint(endpoint, method, data=data, files=files, token=token_to_use)
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