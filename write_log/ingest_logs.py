import json
import boto3
import logging
import uuid
from datetime import datetime, timezone
import os

# Set up logging for the function
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    # All boto3 resource init INSIDE the handler
    table_name = os.environ.get("TABLE_NAME")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    try:
        # Check if the request has a body
        if not event.get("body"):
            logger.error("Request body is missing")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Request body is required"
                }),
            }

        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        elif not isinstance(body, dict):
            logger.error("Invalid body format: %s", type(body))
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Body must be a valid JSON object"
                }),
            }

        # Generate or get log ID, timestamp, severity, and message
        log_id = body.get("id", str(uuid.uuid4()))
        timestamp = datetime.now(timezone.utc).isoformat()
        severity = body.get("severity", "info").lower()
        message = body.get("message", "")

        # Save the log entry to DynamoDB
        table.put_item(
            Item={
                "id": log_id,
                "datetime": timestamp,
                "severity": severity,
                "message": message,
                "partition": "ALL",
            }
        )

        return {
            "statusCode": 201,
            "body": json.dumps({
                "id": log_id,
                "datetime": timestamp
            }),
        }

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Invalid JSON format"
            }),
        }

    except Exception as e:
        logger.exception("Unhandled exception")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Server error: {str(e)}"
            }),
        }
