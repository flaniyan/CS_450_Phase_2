# src/services/artifact_storage.py
"""
DynamoDB-backed storage for artifact metadata.
Replaces in-memory _artifact_storage dictionary.
"""
import boto3
import os
import json
import logging
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")


def get_artifacts_table():
    """Get the DynamoDB table for artifacts"""
    try:
        return dynamodb.Table(ARTIFACTS_TABLE)
    except Exception as e:
        logger.error(f"Error getting artifacts table: {str(e)}")
        raise


def save_artifact(artifact_id: str, artifact_data: Dict[str, Any]) -> bool:
    """
    Save or update an artifact in DynamoDB.

    Args:
        artifact_id: The artifact ID (hash key)
        artifact_data: Dictionary containing artifact metadata

    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_artifacts_table()

        # Prepare item for DynamoDB
        item = {
            "artifact_id": artifact_id,
            "name": artifact_data.get("name", ""),
            "type": artifact_data.get("type", ""),
            "version": artifact_data.get("version", "main"),
            "url": artifact_data.get("url", ""),
        }

        # Add optional fields if present
        if "dataset_name" in artifact_data:
            item["dataset_name"] = artifact_data["dataset_name"]
        if "code_name" in artifact_data:
            item["code_name"] = artifact_data["code_name"]
        if "dataset_id" in artifact_data:
            item["dataset_id"] = artifact_data["dataset_id"]
        if "code_id" in artifact_data:
            item["code_id"] = artifact_data["code_id"]

        table.put_item(Item=item)
        logger.debug(f"Saved artifact {artifact_id} to DynamoDB")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.error(
                f"Error saving artifact {artifact_id}: {error_code} - {str(e)}"
            )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error saving artifact {artifact_id}: {type(e).__name__}: {str(e)}"
        )
        return False


def get_artifact(artifact_id: str) -> Optional[Dict[str, Any]]:
    """
    Get an artifact by ID from DynamoDB.

    Args:
        artifact_id: The artifact ID to retrieve

    Returns:
        Dictionary with artifact data if found, None otherwise
    """
    try:
        table = get_artifacts_table()
        response = table.get_item(Key={"artifact_id": artifact_id})

        if "Item" in response:
            item = response["Item"]
            # Convert DynamoDB item to regular dict
            artifact = {
                "id": item.get("artifact_id"),
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "version": item.get("version", "main"),
                "url": item.get("url", ""),
            }
            # Add optional fields
            if "dataset_name" in item:
                artifact["dataset_name"] = item["dataset_name"]
            if "code_name" in item:
                artifact["code_name"] = item["code_name"]
            if "dataset_id" in item:
                artifact["dataset_id"] = item["dataset_id"]
            if "code_id" in item:
                artifact["code_id"] = item["code_id"]

            return artifact
        return None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.debug(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.error(
                f"Error getting artifact {artifact_id}: {error_code} - {str(e)}"
            )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error getting artifact {artifact_id}: {type(e).__name__}: {str(e)}"
        )
        return None


def update_artifact(artifact_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update specific fields of an artifact in DynamoDB.

    Args:
        artifact_id: The artifact ID to update
        updates: Dictionary of fields to update

    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_artifacts_table()

        # Build update expression
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_values = {}

        for key, value in updates.items():
            attr_name = f"#{key}"
            attr_value = f":{key}"
            update_expr_parts.append(f"{attr_name} = {attr_value}")
            expr_attr_names[attr_name] = key
            expr_attr_values[attr_value] = value

        if not update_expr_parts:
            return True  # Nothing to update

        update_expression = "SET " + ", ".join(update_expr_parts)

        table.update_item(
            Key={"artifact_id": artifact_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
        logger.debug(f"Updated artifact {artifact_id} in DynamoDB")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.error(
                f"Error updating artifact {artifact_id}: {error_code} - {str(e)}"
            )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error updating artifact {artifact_id}: {type(e).__name__}: {str(e)}"
        )
        return False


def delete_artifact(artifact_id: str) -> bool:
    """
    Delete an artifact from DynamoDB.

    Args:
        artifact_id: The artifact ID to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_artifacts_table()
        table.delete_item(Key={"artifact_id": artifact_id})
        logger.debug(f"Deleted artifact {artifact_id} from DynamoDB")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.error(
                f"Error deleting artifact {artifact_id}: {error_code} - {str(e)}"
            )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error deleting artifact {artifact_id}: {type(e).__name__}: {str(e)}"
        )
        return False


def list_all_artifacts() -> List[Dict[str, Any]]:
    """
    List all artifacts from DynamoDB.

    Returns:
        List of artifact dictionaries
    """
    try:
        table = get_artifacts_table()
        artifacts = []

        # Scan the table with ConsistentRead=True to ensure we see all recently written items
        # This matches the behavior of the reference code's _artifact_storage (in-memory dict)
        response = table.scan(ConsistentRead=True)
        artifacts.extend(response.get("Items", []))

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], ConsistentRead=True
            )
            artifacts.extend(response.get("Items", []))

        # Convert DynamoDB items to regular dicts
        result = []
        for item in artifacts:
            artifact = {
                "id": item.get("artifact_id"),
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "version": item.get("version", "main"),
                "url": item.get("url", ""),
            }
            # Add optional fields
            if "dataset_name" in item:
                artifact["dataset_name"] = item["dataset_name"]
            if "code_name" in item:
                artifact["code_name"] = item["code_name"]
            if "dataset_id" in item:
                artifact["dataset_id"] = item["dataset_id"]
            if "code_id" in item:
                artifact["code_id"] = item["code_id"]

            result.append(artifact)

        return result
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.debug(f"Artifacts table doesn't exist yet: {str(e)}")
            return []
        else:
            logger.error(f"Error listing artifacts: {error_code} - {str(e)}")
            return []
    except Exception as e:
        logger.error(
            f"Unexpected error listing artifacts: {type(e).__name__}: {str(e)}"
        )
        return []


def find_artifacts_by_type(artifact_type: str) -> List[Dict[str, Any]]:
    """
    Find all artifacts of a specific type.

    Args:
        artifact_type: The type to filter by (model, dataset, code)

    Returns:
        List of artifact dictionaries
    """
    all_artifacts = list_all_artifacts()
    return [a for a in all_artifacts if a.get("type") == artifact_type]


def find_artifacts_by_name(name: str) -> List[Dict[str, Any]]:
    """
    Find artifacts by name (exact match).

    Args:
        name: The artifact name to search for

    Returns:
        List of artifact dictionaries
    """
    all_artifacts = list_all_artifacts()
    return [a for a in all_artifacts if a.get("name") == name]


def find_models_with_null_link(link_type: str) -> List[Dict[str, Any]]:
    """
    Find models that have NULL dataset_id or code_id but have the corresponding name stored.

    Args:
        link_type: Either "dataset" or "code"

    Returns:
        List of model artifact dictionaries
    """
    all_artifacts = list_all_artifacts()
    models = [a for a in all_artifacts if a.get("type") == "model"]

    if link_type == "dataset":
        return [m for m in models if not m.get("dataset_id") and m.get("dataset_name")]
    elif link_type == "code":
        return [m for m in models if not m.get("code_id") and m.get("code_name")]
    return []


def clear_all_artifacts() -> bool:
    """
    Clear all artifacts from DynamoDB (used for reset).

    Returns:
        True if successful, False otherwise
    """
    try:
        all_artifacts = list_all_artifacts()
        table = get_artifacts_table()

        # Delete all artifacts
        for artifact in all_artifacts:
            artifact_id = artifact.get("id")
            if artifact_id:
                try:
                    table.delete_item(Key={"artifact_id": artifact_id})
                except Exception as e:
                    logger.warning(f"Error deleting artifact {artifact_id}: {str(e)}")

        logger.info(f"Cleared {len(all_artifacts)} artifacts from DynamoDB")
        return True
    except Exception as e:
        logger.error(f"Error clearing artifacts: {type(e).__name__}: {str(e)}")
        return False


def store_generic_artifact_metadata(
    artifact_type: str, artifact_id: str, metadata: Dict[str, Any]
) -> None:
    """
    Store generic artifact metadata in DynamoDB.
    This is the DynamoDB equivalent of the S3 store_generic_artifact_metadata function.

    Args:
        artifact_type: Type of artifact (model, dataset, code)
        artifact_id: The artifact ID
        metadata: Dictionary containing any metadata to store
    """
    try:
        table = get_artifacts_table()

        # Prepare item for DynamoDB
        # Store the full metadata as JSON string for flexibility
        item = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "metadata_json": json.dumps(metadata),
        }

        # Also extract common fields if present for easier querying
        if "name" in metadata:
            item["name"] = str(metadata["name"])
        if "version" in metadata:
            item["version"] = str(metadata.get("version", "main"))
        if "url" in metadata:
            item["url"] = str(metadata["url"])
        if "artifact_id" in metadata:
            item["artifact_id"] = str(metadata["artifact_id"])

        # Store any additional fields from metadata
        for key, value in metadata.items():
            if key not in ["name", "version", "url", "artifact_id", "type"]:
                # Store as string if it's a simple type, otherwise JSON encode
                if isinstance(value, (str, int, float, bool)):
                    item[key] = value
                else:
                    item[key] = json.dumps(value)

        table.put_item(Item=item)
        logger.debug(
            f"Stored generic {artifact_type} metadata for {artifact_id} in DynamoDB"
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.warning(
                f"Failed to store {artifact_type} metadata for {artifact_id}: {error_code} - {str(e)}"
            )
    except Exception as e:
        logger.warning(
            f"Failed to store {artifact_type} metadata for {artifact_id}: {type(e).__name__}: {str(e)}"
        )


def get_generic_artifact_metadata(
    artifact_type: str, artifact_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get generic artifact metadata from DynamoDB.
    This is the DynamoDB equivalent of the S3 get_generic_artifact_metadata function.

    Args:
        artifact_type: Type of artifact (model, dataset, code)
        artifact_id: The artifact ID to retrieve

    Returns:
        Dictionary with metadata if found, None otherwise
    """
    try:
        table = get_artifacts_table()
        response = table.get_item(Key={"artifact_id": artifact_id})

        if "Item" in response:
            item = response["Item"]

            # If metadata_json exists, parse and return it
            if "metadata_json" in item:
                try:
                    metadata = json.loads(item["metadata_json"])
                    return metadata
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse metadata_json for {artifact_id}")

            # Otherwise, reconstruct metadata from individual fields
            metadata = {}

            # Copy all fields from DynamoDB item
            for key, value in item.items():
                if key != "artifact_id":  # artifact_id is the key, not part of metadata
                    # Try to parse JSON strings, otherwise use as-is
                    if isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                            metadata[key] = parsed
                        except (json.JSONDecodeError, TypeError):
                            metadata[key] = value
                    else:
                        metadata[key] = value

            # Ensure artifact_id is in metadata
            metadata["artifact_id"] = artifact_id

            return metadata

        return None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.debug(f"Artifacts table doesn't exist yet: {str(e)}")
        else:
            logger.debug(
                f"Error getting {artifact_type} metadata for {artifact_id}: {error_code} - {str(e)}"
            )
        return None
    except Exception as e:
        logger.debug(
            f"Unexpected error getting {artifact_type} metadata for {artifact_id}: {type(e).__name__}: {str(e)}"
        )
        return None
