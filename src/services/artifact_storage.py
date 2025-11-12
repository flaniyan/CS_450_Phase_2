"""
Artifact Storage Service - DynamoDB Persistence
Persists artifact metadata to DynamoDB for durability across server restarts.
"""
import os
import boto3
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")


def get_artifacts_table():
    """Get the DynamoDB table for artifacts"""
    return dynamodb.Table(ARTIFACTS_TABLE)


def save_artifact_to_db(artifact_id: str, artifact_data: Dict[str, Any]) -> bool:
    """
    Save artifact metadata to DynamoDB.
    
    Args:
        artifact_id: The unique artifact ID
        artifact_data: Dictionary containing name, type, version, url, etc.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_artifacts_table()
        
        item = {
            "artifact_id": artifact_id,
            "name": artifact_data.get("name", ""),
            "type": artifact_data.get("type", "model"),
            "version": artifact_data.get("version", "main"),
            "url": artifact_data.get("url", ""),
        }
        
        # Add any additional fields
        if "id" in artifact_data:
            item["id"] = artifact_data["id"]
        
        table.put_item(Item=item)
        logger.debug(f"Saved artifact {artifact_id} to DynamoDB")
        return True
    except ClientError as e:
        logger.error(f"Error saving artifact {artifact_id} to DynamoDB: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving artifact {artifact_id}: {str(e)}")
        return False


def load_artifact_from_db(artifact_id: str) -> Optional[Dict[str, Any]]:
    """
    Load artifact metadata from DynamoDB.
    
    Args:
        artifact_id: The unique artifact ID
    
    Returns:
        Dictionary with artifact data, or None if not found
    """
    try:
        table = get_artifacts_table()
        response = table.get_item(Key={"artifact_id": artifact_id})
        
        if "Item" in response:
            item = response["Item"]
            return {
                "name": item.get("name", ""),
                "type": item.get("type", "model"),
                "version": item.get("version", "main"),
                "url": item.get("url", ""),
                "id": item.get("id", artifact_id),
            }
        return None
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            # Table doesn't exist yet - that's okay, we'll create it on first write
            logger.debug(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.error(f"Error loading artifact {artifact_id} from DynamoDB: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading artifact {artifact_id}: {str(e)}")
        return None


def load_all_artifacts_from_db() -> Dict[str, Dict[str, Any]]:
    """
    Load all artifacts from DynamoDB.
    
    Returns:
        Dictionary mapping artifact_id to artifact data
    """
    artifacts = {}
    try:
        table = get_artifacts_table()
        response = table.scan()
        
        for item in response.get("Items", []):
            artifact_id = item.get("artifact_id")
            if artifact_id:
                artifacts[artifact_id] = {
                    "name": item.get("name", ""),
                    "type": item.get("type", "model"),
                    "version": item.get("version", "main"),
                    "url": item.get("url", ""),
                    "id": item.get("id", artifact_id),
                }
        
        # Handle pagination if there are more items
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            for item in response.get("Items", []):
                artifact_id = item.get("artifact_id")
                if artifact_id:
                    artifacts[artifact_id] = {
                        "name": item.get("name", ""),
                        "type": item.get("type", "model"),
                        "version": item.get("version", "main"),
                        "url": item.get("url", ""),
                        "id": item.get("id", artifact_id),
                    }
        
        logger.info(f"Loaded {len(artifacts)} artifacts from DynamoDB")
        return artifacts
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            # Table doesn't exist yet - that's okay
            logger.debug(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.error(f"Error loading all artifacts from DynamoDB: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading all artifacts: {str(e)}")
        return {}


def delete_artifact_from_db(artifact_id: str) -> bool:
    """
    Delete artifact metadata from DynamoDB.
    
    Args:
        artifact_id: The unique artifact ID
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_artifacts_table()
        table.delete_item(Key={"artifact_id": artifact_id})
        logger.debug(f"Deleted artifact {artifact_id} from DynamoDB")
        return True
    except ClientError as e:
        logger.error(f"Error deleting artifact {artifact_id} from DynamoDB: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting artifact {artifact_id}: {str(e)}")
        return False


def clear_all_artifacts_from_db() -> bool:
    """
    Clear all artifacts from DynamoDB (used by reset endpoint).
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_artifacts_table()
        
        # Scan and delete all items
        response = table.scan()
        deleted_count = 0
        
        for item in response.get("Items", []):
            artifact_id = item.get("artifact_id")
            if artifact_id:
                table.delete_item(Key={"artifact_id": artifact_id})
                deleted_count += 1
        
        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            for item in response.get("Items", []):
                artifact_id = item.get("artifact_id")
                if artifact_id:
                    table.delete_item(Key={"artifact_id": artifact_id})
                    deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} artifacts from DynamoDB")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            # Table doesn't exist - that's okay, nothing to clear
            logger.debug("Artifacts table doesn't exist, nothing to clear")
            return True
        else:
            logger.error(f"Error clearing artifacts from DynamoDB: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error clearing artifacts: {str(e)}")
        return False

