#!/usr/bin/env python3
"""
Reset Registry Script
Deletes all models, datasets, codes, and packages from S3 and DynamoDB.
Or specifically resets performance/ S3 path if --performance flag is used.

⚠️  WARNING: This is a destructive operation that cannot be undone!

Usage:
    # Use remote API (default):
    python scripts/reset_registry.py
    
    # Use local server:
    python scripts/reset_registry.py --local
    
    # Use custom URL:
    python scripts/reset_registry.py --url http://localhost:8000
    
    # Reset only performance/ S3 path (direct S3 access, bypasses API):
    python scripts/reset_registry.py --performance
    
    # Skip confirmation prompt (for automation):
    python scripts/reset_registry.py --yes
"""
import sys
import os
import requests
import argparse
import boto3
from pathlib import Path
from typing import Optional

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default URLs
DEFAULT_API_URL = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
DEFAULT_LOCAL_URL = "http://localhost:8000"

# AWS Configuration (for performance mode)
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_POINT_NAME = os.getenv("S3_ACCESS_POINT_NAME", "cs450-s3")
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")


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


def get_s3_client_and_arn():
    """Get S3 client and access point ARN for performance mode"""
    try:
        sts = boto3.client("sts", region_name=REGION)
        account_id = sts.get_caller_identity()["Account"]
        ap_arn = f"arn:aws:s3:{REGION}:{account_id}:accesspoint/{ACCESS_POINT_NAME}"
        s3 = boto3.client("s3", region_name=REGION)
        # Test connection
        s3.list_objects_v2(Bucket=ap_arn, Prefix="performance/", MaxKeys=1)
        return s3, ap_arn
    except Exception as e:
        print(f"Error initializing S3: {e}")
        print("Make sure AWS credentials are configured and S3 access point exists")
        return None, None


def reset_performance_s3_path(s3, ap_arn: str) -> bool:
    """
    Reset only the performance/ S3 path by deleting all objects in that prefix.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        deleted_count = 0
        
        print("Deleting all objects in performance/ S3 path...")
        print(f"S3 Access Point: {ap_arn}")
        print(f"Target prefix: performance/")
        
        # Use paginator to handle all objects
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=ap_arn, Prefix="performance/")
        
        all_keys_to_delete = []
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    all_keys_to_delete.append(key)
                    print(f"  Will delete: {key}")
        
        if not all_keys_to_delete:
            print("✓ No objects found in performance/ S3 path")
            return True
        
        print(f"\nTotal objects to delete: {len(all_keys_to_delete)}")
        
        # Delete objects in batches of 1000 (S3 limit)
        batch_size = 1000
        for i in range(0, len(all_keys_to_delete), batch_size):
            batch = all_keys_to_delete[i:i + batch_size]
            objects_to_delete = [{"Key": key} for key in batch]
            
            response = s3.delete_objects(
                Bucket=ap_arn,
                Delete={"Objects": objects_to_delete}
            )
            
            deleted = len(response.get("Deleted", []))
            deleted_count += deleted
            
            if "Errors" in response and response["Errors"]:
                print(f"  ⚠ Errors deleting some objects:")
                for error in response["Errors"]:
                    print(f"    - {error.get('Key')}: {error.get('Message')}")
        
        if deleted_count > 0:
            print(f"\n✓ Deleted {deleted_count} objects from performance/ S3 path")
        
        # Verify deletion
        print("\nVerifying deletion...")
        remaining = list(paginator.paginate(Bucket=ap_arn, Prefix="performance/", MaxKeys=1))
        if remaining and any("Contents" in page and page["Contents"] for page in remaining):
            remaining_count = sum(len(page.get("Contents", [])) for page in remaining if "Contents" in page)
            print(f"  ⚠ Warning: {remaining_count} objects still remain in performance/")
        else:
            print("  ✓ Confirmed: performance/ path is now empty")
        
        return True
    except Exception as e:
        print(f"✗ Error resetting performance/ S3 path: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


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
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Reset only performance/ S3 path (direct S3 access, bypasses API)"
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
    
    # Performance mode: direct S3 reset
    if args.performance:
        return main_performance_mode(args)
    
    # Normal mode: use API
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


def main_performance_mode(args: argparse.Namespace):
    """Main function for performance mode: direct S3 reset of performance/ path"""
    print("=" * 80)
    print("ACME Registry Reset Script - Performance Mode")
    print("(Resets only performance/ S3 path)")
    print("=" * 80)
    print()
    
    # Confirm reset unless --yes flag is used
    if not args.yes:
        print()
        print("⚠️  WARNING: This will DELETE ALL files in the performance/ S3 path!")
        print("   - All models in performance/ will be deleted from S3")
        print("   - This operation CANNOT be undone!")
        print()
        
        response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("Reset cancelled.")
            return 0
    
    # Initialize AWS clients
    print("Initializing AWS clients...")
    s3, ap_arn = get_s3_client_and_arn()
    if not s3 or not ap_arn:
        print("✗ Failed to initialize S3 client")
        return 1
    
    print(f"✓ S3 Access Point: {ap_arn}")
    print()
    
    # Reset performance/ path
    print("Resetting performance/ S3 path...")
    print("=" * 80)
    
    success = reset_performance_s3_path(s3, ap_arn)
    
    print()
    if success:
        print("=" * 80)
        print("✓ Performance S3 path reset completed successfully")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("✗ Performance S3 path reset failed")
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

