"""
Lambda function for downloading model files from S3.
Used for performance testing to compare Lambda vs ECS compute backends.
"""

import json
import os
import base64
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

# Initialize S3 client
region = os.getenv("AWS_REGION", "us-east-1")
access_point_name = os.getenv("S3_ACCESS_POINT_NAME", "cs450-s3")

# Get account ID and construct access point ARN
sts = boto3.client("sts", region_name=region)
account_id = sts.get_caller_identity()["Account"]
ap_arn = f"arn:aws:s3:{region}:{account_id}:accesspoint/{access_point_name}"

# Configure S3 client
s3_config = Config(
    max_pool_connections=50,  # Lambda doesn't need as many connections
    retries={'max_attempts': 3, 'mode': 'standard'}
)
s3 = boto3.client("s3", region_name=region, config=s3_config)


def lambda_handler(event, context):
    """
    Lambda handler for downloading model files from S3.
    
    Expected event structure (from API Gateway):
    {
        "pathParameters": {
            "model_id": "arnir0_Tiny-LLM",
            "version": "main"
        },
        "queryStringParameters": {
            "component": "full"  # optional, defaults to "full"
        }
    }
    
    Returns:
        API Gateway compatible response with base64-encoded file content
    """
    try:
        # Extract path parameters
        path_params = event.get("pathParameters") or {}
        model_id = path_params.get("model_id")
        version = path_params.get("version", "main")
        
        # Extract query parameters
        query_params = event.get("queryStringParameters") or {}
        component = query_params.get("component", "full")
        
        # Determine path prefix (default to performance/ for Lambda performance testing)
        path_prefix = query_params.get("path_prefix", "performance")
        
        if not model_id:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "detail": "Missing required parameter: model_id"
                })
            }
        
        # Construct S3 key
        s3_key = f"{path_prefix}/{model_id}/{version}/model.zip"
        
        # Download from S3
        try:
            response = s3.get_object(Bucket=ap_arn, Key=s3_key)
            file_content = response["Body"].read()
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                return {
                    "statusCode": 404,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps({
                        "detail": f"Model {model_id} version {version} not found"
                    })
                }
            elif error_code == "NoSuchBucket":
                return {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps({
                        "detail": "S3 bucket not found"
                    })
                }
            elif error_code == "AccessDenied":
                return {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps({
                        "detail": "Access denied to S3 bucket"
                    })
                }
            else:
                raise
        
        # Handle component extraction if needed (simplified - just return full for now)
        # TODO: Implement component extraction if needed
        if component != "full":
            # For now, just return full file
            # In production, would extract component from ZIP
            pass
        
        # Encode file content as base64 for API Gateway binary response
        file_content_b64 = base64.b64encode(file_content).decode('utf-8')
        
        # Return API Gateway compatible response
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/zip",
                "Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip",
                "Content-Length": str(len(file_content))
            },
            "body": file_content_b64,
            "isBase64Encoded": True
        }
        
    except Exception as e:
        print(f"Lambda download handler error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "detail": f"Internal server error: {str(e)}"
            })
        }

