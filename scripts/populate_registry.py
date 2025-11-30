#!/usr/bin/env python3
"""
Populate Registry with 500 Real HuggingFace Models

This script populates the ACME Model Registry with 500 real models from HuggingFace,
including the required Tiny-LLM model for performance testing.

Usage:
    # Use remote API (default):
    python scripts/populate_registry.py
    
    # Use local server:
    python scripts/populate_registry.py --local
    
    # Use custom URL:
    python scripts/populate_registry.py --url http://localhost:8000
    
    # Or with environment variable:
    API_BASE_URL=http://localhost:3000 python scripts/populate_registry.py
"""
import sys
import os
import time
import requests
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default URLs
DEFAULT_API_URL = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
DEFAULT_LOCAL_URL = "http://localhost:8000"

HF_API_BASE = "https://huggingface.co/api"
MAX_RETRIES = 3
RETRY_DELAY = 2

# Required model (must be included)
REQUIRED_MODEL = "arnir0/Tiny-LLM"

# Import the hardcoded list of 500 models
try:
    from scripts.huggingface_models_list import HF_MODELS_500
    POPULAR_MODELS = HF_MODELS_500
except ImportError:
    # Fallback if import fails - use minimal list
    POPULAR_MODELS = [
        "arnir0/Tiny-LLM",
        "bert-base-uncased",
        "distilbert-base-uncased",
        "roberta-base",
        "gpt2",
        "t5-small",
        "t5-base",
        "facebook/bart-base",
    ]


def get_authentication_token(api_base_url: str) -> Optional[str]:
    """Get authentication token for API requests"""
    try:
        response = requests.put(
            f"{api_base_url}/authenticate",
            json={
                "user": {
                    "name": "ece30861defaultadminuser",
                    "is_admin": True
                },
                "secret": {
                    "password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
                }
            },
            timeout=10
        )
        if response.status_code == 200:
            token = response.text.strip('"')
            return token
        else:
            print(f"Warning: Authentication failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"Warning: Could not authenticate: {e}")
        return None


def get_hardcoded_models(count: int = 500) -> List[str]:
    """
    Get hardcoded list of 500 real HuggingFace models.
    No API calls - just returns the pre-defined list.
    """
    models = POPULAR_MODELS.copy()
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
        models.insert(0, REQUIRED_MODEL)
    
    # Limit to exactly count
    models = models[:count]
    
    return models


# Removed check_model_exists - we'll skip existence checks and just ingest


def ingest_model(api_base_url: str, model_id: str, auth_token: Optional[str], retry: int = 0) -> bool:
    """Ingest a single model into the registry"""
    try:
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["X-Authorization"] = auth_token
        
        # Use the /artifact/model endpoint to ingest
        url = f"{api_base_url}/artifact/model"
        payload = {
            "url": f"https://huggingface.co/{model_id}"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        
        if response.status_code in [200, 201, 202]:
            print(f"✓ Successfully ingested: {model_id}")
            return True
        elif response.status_code == 409:
            print(f"⊘ Already exists: {model_id} (skipping)")
            return True  # Consider existing models as success
        else:
            print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {response.text[:200]}")
            if retry < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY}s... (attempt {retry + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return ingest_model(api_base_url, model_id, auth_token, retry + 1)
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout ingesting {model_id}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model(api_base_url, model_id, auth_token, retry + 1)
        return False
    except Exception as e:
        print(f"✗ Error ingesting {model_id}: {str(e)}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model(api_base_url, model_id, auth_token, retry + 1)
        return False


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Populate ACME Model Registry with 500 HuggingFace models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/populate_registry.py              # Use remote API (default)
  python scripts/populate_registry.py --local      # Use local server (localhost:8000)
  python scripts/populate_registry.py --url http://localhost:3000  # Use custom URL
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--local",
        action="store_true",
        help=f"Use local server at {DEFAULT_LOCAL_URL}"
    )
    group.add_argument(
        "--url",
        type=str,
        metavar="URL",
        help="Custom API base URL (e.g., http://localhost:8000)"
    )
    
    return parser.parse_args()


def get_api_base_url(args: argparse.Namespace) -> str:
    """Determine the API base URL from arguments or environment"""
    # Priority: CLI args > environment variable > default
    if args.url:
        return args.url.rstrip("/")
    elif args.local:
        return DEFAULT_LOCAL_URL
    elif os.getenv("API_BASE_URL"):
        return os.getenv("API_BASE_URL").rstrip("/")
    else:
        return DEFAULT_API_URL


def main():
    """Main function to populate registry with 500 models"""
    # Parse command-line arguments
    args = parse_arguments()
    api_base_url = get_api_base_url(args)
    
    print("=" * 80)
    print("ACME Model Registry Population Script")
    print("=" * 80)
    print(f"API Base URL: {api_base_url}")
    if args.local:
        print("Mode: Local")
    elif args.url:
        print(f"Mode: Custom URL")
    elif os.getenv("API_BASE_URL"):
        print("Mode: Environment Variable")
    else:
        print("Mode: Remote API (default)")
    print()
    
    # Get authentication token
    print("Authenticating...")
    auth_token = get_authentication_token(api_base_url)
    if auth_token:
        print("✓ Authentication successful")
    else:
        print("⊘ No authentication token (some endpoints may fail)")
    print()
    
    # Get hardcoded list of 500 models
    print("Loading hardcoded list of 500 HuggingFace models...")
    models = get_hardcoded_models(count=500)
    print(f"✓ Loaded {len(models)} models to ingest")
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
    models.insert(0, REQUIRED_MODEL)
    models = models[:500]  # Ensure exactly 500
    
    print(f"Will ingest {len(models)} models (starting with {REQUIRED_MODEL})")
    print()
    
    # Start ingesting models (skip existence check - just ingest, API will handle duplicates)
    print("Starting model ingestion...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    skipped = 0
    
    for i, model_id in enumerate(models, 1):
        print(f"[{i}/{len(models)}] Ingesting: {model_id}")
        
        result = ingest_model(api_base_url, model_id, auth_token)
        if result:
            successful += 1
        else:
            failed += 1
        
        # Small delay to avoid rate limiting
        if i < len(models):
            time.sleep(0.5)
        
        # Progress update every 50 models
        if i % 50 == 0:
            print()
            print(f"Progress: {i}/{len(models)} ({successful} successful, {failed} failed)")
            print()
    
    # Final summary
    print()
    print("=" * 80)
    print("Ingestion Summary")
    print("=" * 80)
    print(f"Total models processed: {len(models)}")
    print(f"  - Successfully ingested: {successful}")
    print(f"  - Failed: {failed}")
    print(f"Total successful: {successful}")
    print()
    
    # Verify Tiny-LLM was in the list
    if REQUIRED_MODEL in models:
        print(f"✓ Required model '{REQUIRED_MODEL}' was included in ingestion list")
    
    if successful >= 500:
        print("✓ Registry should have 500+ models")
        return 0
    else:
        print(f"⚠ Successfully ingested {successful} models (target: 500)")
        return 1 if failed > successful else 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

