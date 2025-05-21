import boto3
import json
import os
import time
import base64
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from typing import Dict, Any, Optional, Tuple

# --- Constants and Configuration ---

MAX_LIMIT = 100
VALID_SEVERITIES = frozenset({"info", "warning", "error"})
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}
PROJECTION_FIELDS = os.environ.get(
    "PROJECTION_FIELDS", "id,severity,#datetime,message"
).split(",")
EXPRESSION_ATTRIBUTE_NAMES = {"#datetime": "datetime"}

# --- Logging and Metrics ---

logger = Logger(service="LogQueryService")
metrics = Metrics(namespace="LogQueryService")

# --- DynamoDB Setup ---

TABLE_NAME = os.environ.get("TABLE_NAME")
if not TABLE_NAME:
    logger.error("Environment variable TABLE_NAME is required")
    raise RuntimeError("TABLE_NAME not configured")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def validate_projection_fields():
    """Log a warning if projection fields are not part of table schema (key/index fields only)."""
    try:
        response = dynamodb.meta.client.describe_table(TableName=TABLE_NAME)
        indexed_fields = {
            attr["AttributeName"] for attr in response["Table"]["AttributeDefinitions"]
        }
        projection_attributes = {
            field
            for field in PROJECTION_FIELDS
            if field not in EXPRESSION_ATTRIBUTE_NAMES
        }
        unindexed_fields = projection_attributes - indexed_fields
        if unindexed_fields:
            logger.warning(
                f"The following projection fields are not defined in the index schema: {unindexed_fields}"
            )
    except ClientError as e:
        logger.warning(f"Could not validate table schema: {e}")


validate_projection_fields()

# --- Helpers ---


def build_response(status_code: int, body: Dict) -> Dict:
    return {
        "statusCode": status_code,
        "headers": DEFAULT_HEADERS,
        "body": json.dumps(body, default=str, indent=2),
    }


def encode_start_key(start_key: Dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


def decode_start_key(encoded_key: str) -> Dict:
    try:
        return json.loads(base64.urlsafe_b64decode(encoded_key).decode())
    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Invalid pagination token: {e}")
        raise ValueError("Invalid or tampered pagination token")


def validate_start_key(start_key: Any, severity: Optional[str] = None) -> bool:
    if not isinstance(start_key, dict):
        return False
    required_keys = {"severity", "datetime"} if severity else {"partition", "datetime"}
    return all(key in start_key for key in required_keys)


def execute_query(
    index_name: str, key_condition, limit: int, start_key: Optional[Dict] = None
) -> Tuple[list, bool, Optional[str]]:
    params = {
        "IndexName": index_name,
        "KeyConditionExpression": key_condition,
        "ScanIndexForward": False,
        "Limit": limit,
        "ProjectionExpression": ",".join(PROJECTION_FIELDS),
        "ExpressionAttributeNames": EXPRESSION_ATTRIBUTE_NAMES,
    }
    if start_key:
        params["ExclusiveStartKey"] = start_key

    start_time = time.time()
    try:
        response = table.query(**params)
        latency = (time.time() - start_time) * 1000
        metrics.add_metric(
            name=f"{index_name}QueryLatency",
            unit=MetricUnit.Milliseconds,
            value=latency,
        )
        items = response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")
        has_more = bool(last_key)
        encoded_key = encode_start_key(last_key) if has_more else None
        return items, has_more, encoded_key
    except Exception as e:
        metrics.add_metric(
            name=f"{index_name}QueryErrors", unit=MetricUnit.Count, value=1
        )
        logger.error(f"Error in execute_query: {e}", exc_info=True)
        raise


# --- Lambda Handler ---


@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict, context: Any) -> Dict:
    try:
        query_params = event.get("queryStringParameters") or {}
        severity = query_params.get("severity", "").strip().lower()

        try:
            limit = min(int(query_params.get("limit", MAX_LIMIT)), MAX_LIMIT)
            if limit <= 0:
                raise ValueError("Limit must be positive")
        except ValueError as e:
            return build_response(400, {"error": str(e)})

        start_key = None
        if "startKey" in query_params and query_params["startKey"]:
            try:
                start_key = decode_start_key(query_params["startKey"])
                if not validate_start_key(start_key, severity):
                    return build_response(
                        400, {"error": "Invalid pagination token structure"}
                    )
            except ValueError as e:
                return build_response(400, {"error": str(e)})

        logger.info(
            "Processing log request",
            extra={
                "severity": severity,
                "limit": limit,
                "has_start_key": bool(start_key),
            },
        )

        if severity:
            if severity not in VALID_SEVERITIES:
                return build_response(
                    400,
                    {
                        "error": f"Invalid severity. Must be one of {sorted(VALID_SEVERITIES)}"
                    },
                )
            items, has_more, next_token = execute_query(
                "severityindex", Key("severity").eq(severity), limit, start_key
            )
        else:
            items, has_more, next_token = execute_query(
                "alldatetimeindex", Key("partition").eq("ALL"), limit, start_key
            )

        if not items:
            return build_response(
                200, {"message": "No logs found", "items": [], "hasMore": False}
            )

        response_body = {"items": items, "hasMore": has_more}
        if has_more:
            response_body["nextToken"] = next_token

        return build_response(200, response_body)

    except ClientError as e:
        logger.error(f"DynamoDB error: {e}", exc_info=True)
        metrics.add_metric(name="DynamoDBErrors", unit=MetricUnit.Count, value=1)
        return build_response(500, {"error": "Database operation failed"})

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        metrics.add_metric(name="SystemErrors", unit=MetricUnit.Count, value=1)
        return build_response(500, {"error": "Internal server error"})
