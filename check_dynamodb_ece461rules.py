#!/usr/bin/env python3
"""
Script to search DynamoDB artifacts table for "ece461rules" in model names and metadata.
"""
import boto3
import os
import json
from typing import Dict, Any, List

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

def search_for_ece461rules() -> List[Dict[str, Any]]:
    """
    Search DynamoDB artifacts table for any mentions of "ece461rules"
    in model names, metadata, or any text fields.
    """
    try:
        table = dynamodb.Table(ARTIFACTS_TABLE)
        matches = []
        
        print(f"Scanning DynamoDB table: {ARTIFACTS_TABLE}")
        print(f"Search term: 'ece461rules'")
        print("-" * 80)
        
        # Scan the entire table
        response = table.scan()
        items = response.get("Items", [])
        
        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        
        print(f"Total artifacts found: {len(items)}")
        print("-" * 80)
        
        # Search for "ece461rules" in all fields
        search_term = "ece461rules"
        search_term_lower = search_term.lower()
        
        for item in items:
            artifact_id = item.get("artifact_id", "")
            artifact_name = item.get("name", "")
            artifact_type = item.get("type", "")
            
            # Check all string fields
            found_in_fields = []
            
            # Check name field
            if search_term_lower in str(artifact_name).lower():
                found_in_fields.append(f"name: '{artifact_name}'")
            
            # Check all string fields in the item
            for key, value in item.items():
                if isinstance(value, str):
                    if search_term_lower in value.lower():
                        if key not in ["name"]:  # Already checked name
                            found_in_fields.append(f"{key}: '{value[:100]}...'")  # Truncate long values
            
            # Check metadata_json if it exists
            if "metadata_json" in item:
                try:
                    metadata = json.loads(item["metadata_json"])
                    metadata_str = json.dumps(metadata).lower()
                    if search_term_lower in metadata_str:
                        found_in_fields.append("metadata_json: (contains search term)")
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # If found in any field, add to matches
            if found_in_fields:
                match_info = {
                    "artifact_id": artifact_id,
                    "name": artifact_name,
                    "type": artifact_type,
                    "version": item.get("version", ""),
                    "url": item.get("url", ""),
                    "found_in": found_in_fields,
                    "full_item": item
                }
                matches.append(match_info)
        
        return matches
        
    except Exception as e:
        print(f"Error scanning DynamoDB: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Main function to run the search"""
    print("=" * 80)
    print("Searching DynamoDB for 'ece461rules'")
    print("=" * 80)
    print()
    
    matches = search_for_ece461rules()
    
    print()
    print("=" * 80)
    print(f"RESULTS: Found {len(matches)} artifact(s) containing 'ece461rules'")
    print("=" * 80)
    print()
    
    if matches:
        for i, match in enumerate(matches, 1):
            print(f"Match {i}:")
            print(f"  Artifact ID: {match['artifact_id']}")
            print(f"  Name: {match['name']}")
            print(f"  Type: {match['type']}")
            print(f"  Version: {match['version']}")
            print(f"  URL: {match['url']}")
            print(f"  Found in fields: {', '.join(match['found_in'])}")
            print()
            print("  Full item:")
            print(json.dumps(match['full_item'], indent=2, default=str))
            print("-" * 80)
            print()
    else:
        print("No artifacts found containing 'ece461rules'")
        print()
        print("Note: This search only checks the DynamoDB artifacts table.")
        print("Model card/README data might be stored in S3, not DynamoDB.")


if __name__ == "__main__":
    main()

