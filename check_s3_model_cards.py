#!/usr/bin/env python3
"""
Script to search S3 for model cards/README files containing "ece461rules".
Also lists all model names to check for similar matches.
"""
import boto3
import os
import json
import re
from typing import Dict, Any, List

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AP_ARN = os.getenv("AP_ARN", "pkg-artifacts")

# Initialize S3
s3 = boto3.client("s3", region_name=AWS_REGION)

def list_all_models() -> List[str]:
    """List all model names from S3"""
    try:
        models = []
        prefix = "models/"
        
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=AP_ARN, Prefix=prefix, Delimiter="/")
        
        for page in pages:
            # Get model names from common prefixes
            if "CommonPrefixes" in page:
                for prefix_info in page["CommonPrefixes"]:
                    model_path = prefix_info["Prefix"]
                    # Extract model name (remove "models/" prefix and trailing "/")
                    model_name = model_path.replace("models/", "").rstrip("/")
                    if model_name:
                        models.append(model_name)
        
        return sorted(set(models))
    except Exception as e:
        print(f"Error listing models from S3: {str(e)}")
        return []


def search_model_cards_for_ece461rules() -> List[Dict[str, Any]]:
    """
    Search S3 model card/README files for "ece461rules"
    """
    try:
        matches = []
        search_term = "ece461rules"
        search_term_lower = search_term.lower()
        
        print(f"Searching S3 bucket: {AP_ARN}")
        print(f"Search term: 'ece461rules'")
        print("-" * 80)
        
        # List all models
        models = list_all_models()
        print(f"Found {len(models)} models in S3")
        print("-" * 80)
        
        # Check each model for README/metadata files
        for model_name in models:
            # Try common versions
            versions = ["main", "1.0.0", "latest", "master"]
            
            for version in versions:
                # Try to find README files
                readme_keys = [
                    f"models/{model_name}/{version}/README.md",
                    f"models/{model_name}/{version}/readme.md",
                    f"models/{model_name}/{version}/README.txt",
                    f"models/{model_name}/{version}/readme.txt",
                    f"models/{model_name}/{version}/metadata.json",
                ]
                
                for key in readme_keys:
                    try:
                        response = s3.get_object(Bucket=AP_ARN, Key=key)
                        content = response["Body"].read().decode("utf-8", errors="ignore")
                        
                        if search_term_lower in content.lower():
                            matches.append({
                                "model_name": model_name,
                                "version": version,
                                "file": key,
                                "match_context": _extract_context(content, search_term_lower, 200)
                            })
                    except s3.exceptions.NoSuchKey:
                        continue
                    except Exception as e:
                        # Skip errors for individual files
                        continue
        
        return matches
        
    except Exception as e:
        print(f"Error searching S3: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def _extract_context(text: str, search_term: str, context_length: int = 200) -> str:
    """Extract context around the search term"""
    text_lower = text.lower()
    index = text_lower.find(search_term.lower())
    
    if index == -1:
        return ""
    
    start = max(0, index - context_length)
    end = min(len(text), index + len(search_term) + context_length)
    
    context = text[start:end]
    # Highlight the match
    context = context.replace(
        text[index:index+len(search_term)],
        f"***{text[index:index+len(search_term)]}***"
    )
    
    return context


def check_model_names_for_similar() -> List[str]:
    """Check model names for anything similar to 'ece461rules'"""
    models = list_all_models()
    search_term = "ece461rules"
    search_term_lower = search_term.lower()
    
    similar = []
    for model_name in models:
        model_lower = model_name.lower()
        # Check if model name contains parts of the search term
        if (search_term_lower in model_lower or 
            "ece461" in model_lower or 
            "rules" in model_lower and "ece" in model_lower):
            similar.append(model_name)
    
    return similar


def main():
    """Main function"""
    print("=" * 80)
    print("Searching S3 for 'ece461rules' in model cards and model names")
    print("=" * 80)
    print()
    
    # Check model names
    print("Checking model names for similar matches...")
    similar_names = check_model_names_for_similar()
    if similar_names:
        print(f"Found {len(similar_names)} model name(s) that might be related:")
        for name in similar_names:
            print(f"  - {name}")
    else:
        print("No similar model names found.")
    print()
    
    # Search model cards
    print("Searching model card/README files in S3...")
    matches = search_model_cards_for_ece461rules()
    
    print()
    print("=" * 80)
    print(f"RESULTS: Found {len(matches)} model card(s) containing 'ece461rules'")
    print("=" * 80)
    print()
    
    if matches:
        for i, match in enumerate(matches, 1):
            print(f"Match {i}:")
            print(f"  Model: {match['model_name']}")
            print(f"  Version: {match['version']}")
            print(f"  File: {match['file']}")
            print(f"  Context: {match['match_context'][:500]}...")
            print("-" * 80)
            print()
    else:
        print("No model cards/README files found containing 'ece461rules'")
        print()


if __name__ == "__main__":
    main()

