#!/usr/bin/env python3
"""
List all model names from DynamoDB to check for any variations of "ece461rules"
"""
import boto3
import os
import json
from typing import Dict, Any, List
from collections import Counter

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

def list_all_model_names() -> List[Dict[str, Any]]:
    """List all model names from DynamoDB"""
    try:
        table = dynamodb.Table(ARTIFACTS_TABLE)
        models = []
        
        print(f"Scanning DynamoDB table: {ARTIFACTS_TABLE}")
        print("-" * 80)
        
        # Scan the entire table
        response = table.scan()
        items = response.get("Items", [])
        
        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        
        # Filter for models
        for item in items:
            if item.get("type") == "model":
                model_info = {
                    "artifact_id": item.get("artifact_id", ""),
                    "name": item.get("name", ""),
                    "version": item.get("version", ""),
                    "url": item.get("url", ""),
                }
                models.append(model_info)
        
        return models
        
    except Exception as e:
        print(f"Error scanning DynamoDB: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def search_for_variations(models: List[Dict[str, Any]], search_term: str = "ece461rules") -> List[Dict[str, Any]]:
    """Search for variations of the search term"""
    search_lower = search_term.lower()
    variations = []
    
    # Check for partial matches
    keywords = ["ece461", "rules", "ece", "461"]
    
    for model in models:
        model_name = model.get("name", "").lower()
        
        # Check for exact match
        if search_lower in model_name:
            variations.append({**model, "match_type": "exact"})
        # Check for keyword matches
        elif any(keyword in model_name for keyword in keywords):
            variations.append({**model, "match_type": "partial"})
    
    return variations


def main():
    """Main function"""
    print("=" * 80)
    print("Listing all model names from DynamoDB")
    print("=" * 80)
    print()
    
    models = list_all_model_names()
    
    print(f"Total models found: {len(models)}")
    print()
    
    # Search for variations
    print(f"Searching for variations of 'ece461rules'...")
    variations = search_for_variations(models, "ece461rules")
    
    if variations:
        print(f"Found {len(variations)} potential matches:")
        print("-" * 80)
        for model in variations:
            print(f"  [{model['match_type']}] {model['name']}")
            print(f"    ID: {model['artifact_id']}")
            print(f"    URL: {model['url']}")
            print()
    else:
        print("No variations found.")
        print()
    
    # List all model names
    print("=" * 80)
    print("All model names in DynamoDB:")
    print("=" * 80)
    for i, model in enumerate(models, 1):
        print(f"{i:3d}. {model['name']} (ID: {model['artifact_id']})")
    
    print()
    print("=" * 80)
    print("Summary:")
    print(f"  Total models: {len(models)}")
    print(f"  Potential matches for 'ece461rules': {len(variations)}")
    print("=" * 80)


if __name__ == "__main__":
    main()

