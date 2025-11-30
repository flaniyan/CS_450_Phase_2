#!/usr/bin/env python3
"""
Reset Registry Script
Deletes all models, datasets, codes, and packages from S3 and DynamoDB.

⚠️  WARNING: This is a destructive operation that cannot be undone!

Usage:
    # Use remote API (default):
    python scripts/reset_registry.py
    
    # Use local server:
    python scripts/reset_registry.py --local
    
    # Use custom URL:
    python scripts/reset_registry.py --url http://localhost:8000
    
    # Skip confirmation prompt (for automation):
    python scripts/reset_registry.py --yes
"""
import sys
import os
import requests
import argparse
from pathlib import Path
from typing import Optional

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default URLs
DEFAULT_API_URL = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
DEFAULT_LOCAL_URL = "http://localhost:8000"


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


def reset_registry(api_base_url: str, auth_token: Optional[str]) -> bool:
    """
    Reset the registry by calling the DELETE /reset endpoint.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["X-Authorization"] = auth_token
        
        url = f"{api_base_url}/reset"
        
        print(f"Calling DELETE {url}...")
        response = requests.delete(url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            print("✓ Registry reset successful!")
            return True
        else:
            print(f"✗ Reset failed: HTTP {response.status_code}")
            if response.text:
                print(f"  Error: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ Timeout - reset operation took too long")
        return False
    except Exception as e:
        print(f"✗ Error resetting registry: {str(e)}")
        return False


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Reset ACME Model Registry (WARNING: Destructive operation!)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/reset_registry.py              # Use remote API (default)
  python scripts/reset_registry.py --local      # Use local server (localhost:8000)
  python scripts/reset_registry.py --url http://localhost:3000  # Use custom URL
  python scripts/reset_registry.py --yes        # Skip confirmation prompt
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
    
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)"
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


def confirm_reset() -> bool:
    """Ask user to confirm the reset operation"""
    print()
    print("⚠️  WARNING: This will DELETE ALL data from the registry!")
    print("   - All models will be deleted from S3")
    print("   - All datasets will be deleted from S3")
    print("   - All code artifacts will be deleted from S3")
    print("   - All packages will be deleted from S3")
    print("   - All artifacts will be deleted from DynamoDB")
    print("   - This operation CANNOT be undone!")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    return response in ["yes", "y"]


def main():
    """Main function to reset the registry"""
    # Parse command-line arguments
    args = parse_arguments()
    api_base_url = get_api_base_url(args)
    
    print("=" * 80)
    print("ACME Model Registry Reset Script")
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
    
    # Confirm reset unless --yes flag is used
    if not args.yes:
        if not confirm_reset():
            print("Reset cancelled.")
            return 0
    
    # Get authentication token
    print("Authenticating...")
    auth_token = get_authentication_token(api_base_url)
    if auth_token:
        print("✓ Authentication successful")
    else:
        print("✗ Authentication failed - cannot proceed without admin token")
        return 1
    print()
    
    # Reset the registry
    print("Resetting registry...")
    print("=" * 80)
    
    success = reset_registry(api_base_url, auth_token)
    
    print()
    if success:
        print("=" * 80)
        print("✓ Registry reset completed successfully")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("✗ Registry reset failed")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nReset cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

