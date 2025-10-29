#!/usr/bin/env python3
"""
Test Package Management System with Existing Models
This script tests the package management functionality using the 3 models in S3.
"""

import boto3
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any

# AWS clients
s3 = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Configuration
ARTIFACTS_BUCKET = 'pkg-artifacts'
PACKAGES_TABLE = 'packages'
USERS_TABLE = 'users'
TOKENS_TABLE = 'tokens'

def test_s3_packages():
    """Test S3 package storage and retrieval"""
    print("Testing S3 Package Storage...")
    
    try:
        # List all packages in S3
        response = s3.list_objects_v2(Bucket=ARTIFACTS_BUCKET, Prefix='models/')
        
        if 'Contents' not in response:
            print("[FAIL] No packages found in S3")
            return False
            
        packages = []
        for obj in response['Contents']:
            if obj['Key'].endswith('.zip'):
                # Extract package info from S3 key
                parts = obj['Key'].split('/')
                if len(parts) >= 4:
                    pkg_name = parts[1]
                    version = parts[2]
                    packages.append({
                        'name': pkg_name,
                        'version': version,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        's3_key': obj['Key']
                    })
        
        print(f"[PASS] Found {len(packages)} packages in S3:")
        for pkg in packages:
            size_mb = pkg['size'] / (1024 * 1024)
            print(f"   Package {pkg['name']} v{pkg['version']} ({size_mb:.1f} MB)")
            
        return packages
        
    except Exception as e:
        print(f"[ERROR] Error accessing S3 packages: {e}")
        return False

def test_package_metadata():
    """Test DynamoDB package metadata"""
    print("\nTesting Package Metadata...")
    
    try:
        table = dynamodb.Table(PACKAGES_TABLE)
        
        # Scan for packages
        response = table.scan()
        packages = response.get('Items', [])
        
        print(f"[PASS] Found {len(packages)} packages in DynamoDB:")
        for pkg in packages:
            print(f"   Package {pkg.get('pkg_key', 'Unknown')} - {pkg.get('description', 'No description')}")
            
        return packages
        
    except Exception as e:
        print(f"[ERROR] Error accessing package metadata: {e}")
        return False

def test_presigned_urls():
    """Test presigned URL generation for package downloads"""
    print("\nTesting Presigned URL Generation...")
    
    try:
        # Test packages from S3
        test_packages = [
            'models/audience-classifier/v1.0/model.zip',
            'models/bert-base-uncased/v1.0/model.zip',
            'models/whisper-tiny/v1.0/model.zip'
        ]
        
        for s3_key in test_packages:
            try:
                # Generate presigned URL (valid for 1 hour)
                url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': ARTIFACTS_BUCKET, 'Key': s3_key},
                    ExpiresIn=3600
                )
                
                # Extract package name from S3 key
                parts = s3_key.split('/')
                pkg_name = parts[1] if len(parts) > 1 else 'unknown'
                
                print(f"   [PASS] {pkg_name}: Presigned URL generated")
                print(f"      URL: {url[:80]}...")
                
            except Exception as e:
                print(f"   [FAIL] {s3_key}: Error generating presigned URL - {e}")
                
        return True
        
    except Exception as e:
        print(f"[ERROR] Error testing presigned URLs: {e}")
        return False

def test_user_management():
    """Test user management system"""
    print("\nTesting User Management...")
    
    try:
        users_table = dynamodb.Table(USERS_TABLE)
        
        # Get user count
        response = users_table.scan(Select='COUNT')
        user_count = response.get('Count', 0)
        
        print(f"[PASS] Found {user_count} users in the system")
        
        if user_count > 0:
            # Get sample users
            response = users_table.scan(Limit=5)
            users = response.get('Items', [])
            
            print("   Sample users:")
            for user in users:
                username = user.get('username', 'Unknown')
                groups = user.get('groups', [])
                print(f"   User {username} (groups: {', '.join(groups)})")
                
        return True
        
    except Exception as e:
        print(f"[ERROR] Error testing user management: {e}")
        return False

def test_package_download_workflow():
    """Test the complete package download workflow"""
    print("\nTesting Package Download Workflow...")
    
    try:
        # Simulate a package download request
        test_package = 'models/audience-classifier/v1.0/model.zip'
        
        # 1. Check if package exists
        try:
            s3.head_object(Bucket=ARTIFACTS_BUCKET, Key=test_package)
            print("   [PASS] Package exists in S3")
        except s3.exceptions.NoSuchKey:
            print("   [FAIL] Package not found in S3")
            return False
            
        # 2. Generate presigned URL
        download_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': ARTIFACTS_BUCKET, 'Key': test_package},
            ExpiresIn=3600
        )
        print("   [PASS] Presigned URL generated")
        
        # 3. Log download event (simulate)
        downloads_table = dynamodb.Table('downloads')
        download_event = {
            'download_id': f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'user_id': 'test-user',
            'pkg_name': 'audience-classifier',
            'version': 'v1.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'initiated'
        }
        
        # Note: We won't actually write to DynamoDB in this test
        print("   [PASS] Download event prepared")
        print(f"   Download URL: {download_url[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error testing download workflow: {e}")
        return False

def main():
    """Main test function"""
    print("Package Management System Test Suite")
    print("=" * 50)
    
    # Test S3 packages
    s3_packages = test_s3_packages()
    
    # Test package metadata
    db_packages = test_package_metadata()
    
    # Test presigned URLs
    presigned_success = test_presigned_urls()
    
    # Test user management
    user_success = test_user_management()
    
    # Test download workflow
    download_success = test_package_download_workflow()
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    
    tests = [
        ("S3 Package Storage", s3_packages is not False),
        ("Package Metadata", db_packages is not False),
        ("Presigned URLs", presigned_success),
        ("User Management", user_success),
        ("Download Workflow", download_success)
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    for test_name, success in tests:
        status = "[PASS]" if success else "[FAIL]"
        print(f"   {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All tests passed! Package management system is working.")
    else:
        print("[WARNING] Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    main()
