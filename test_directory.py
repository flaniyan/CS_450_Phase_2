#!/usr/bin/env python3
"""
Test script to verify directory page shows packages
"""
import requests
import json

def test_directory_page():
    """Test that the directory page shows packages"""
    
    base_url = "http://localhost:3000"
    
    try:
        print("Testing directory page...")
        response = requests.get(f"{base_url}/directory")
        
        if response.status_code == 200:
            content = response.text
            
            # Check if the package name appears in the HTML
            if "sample-bert-model" in content:
                print("[SUCCESS] Directory page shows the test package!")
                print("Package 'sample-bert-model' found in directory page")
                return True
            else:
                print("[INFO] Directory page loaded but package not visible")
                print("This might be because the server needs to be restarted")
                return False
        else:
            print(f"[ERROR] Directory page failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error testing directory: {str(e)}")
        return False

def test_api_packages():
    """Test that the API still shows packages"""
    
    base_url = "http://localhost:3000"
    
    try:
        print("\nTesting API packages endpoint...")
        response = requests.get(f"{base_url}/api/packages")
        
        if response.status_code == 200:
            result = response.json()
            packages = result.get("packages", [])
            
            if packages:
                print(f"[SUCCESS] API shows {len(packages)} package(s):")
                for pkg in packages:
                    print(f"  - {pkg['name']} version {pkg['version']}")
                return True
            else:
                print("[INFO] API shows no packages")
                return False
        else:
            print(f"[ERROR] API failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error testing API: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing Directory Page Package Display")
    print("=" * 50)
    
    # Test API first
    api_success = test_api_packages()
    
    # Test directory page
    directory_success = test_directory_page()
    
    print("\n" + "=" * 50)
    if api_success and directory_success:
        print("All tests passed! Directory shows packages correctly.")
    elif api_success and not directory_success:
        print("API works but directory page needs server restart.")
        print("Please restart the server with: python -m src.index")
    else:
        print("Some tests failed. Check the output above.")
