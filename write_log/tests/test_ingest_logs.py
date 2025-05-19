import json
import boto3
import logging
import uuid
from datetime import datetime, timezone
import os
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.environ.get("TABLE_NAME"))
    try:
        # --- Support query endpoint ---
        if event.get("queryStringParameters") is not None:
            # Query the 100 most recent logs
            result = table.query(
                KeyConditionExpression=None,  # Use correct KeyCondition in real usage
                Limit=100,
                ScanIndexForward=False
            )
            items = result.get("Items", [])
            last_key = result.get("LastEvaluatedKey")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "items": items,
                    "hasMore": last_key is not None
                }),
            }

        # --- Write log endpoint ---
        if not event.get("body"):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Request body is required"}),
            }
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        if not isinstance(body, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Body must be a valid JSON object"}),
            }
        # Validate fields
        severity = body.get("severity")
        message = body.get("message")
        if severity is None or message is None:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required fields: severity, message"}),
            }
        if severity.lower() not in ("info", "warning", "error"):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid severity"}),
            }
        log_id = body.get("id", str(uuid.uuid4()))
        # Use UTC with timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            table.put_item(
                Item={
                    "id": log_id,
                    "datetime": timestamp,
                    "severity": severity.lower(),
                    "message": message,
                    "partition": "ALL",
                }
            )
        except ClientError as e:
            logger.exception("Database operation failed")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Database operation failed"}),
            }
        return {
            "statusCode": 201,
            "body": json.dumps({"id": log_id, "datetime": timestamp}),
        }
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON format"}),
        }
    except Exception as e:
        logger.exception("Unhandled exception")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Server error: {str(e)}"}),
        }
