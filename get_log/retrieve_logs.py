import boto3
import json
import os
import time
import base64
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit


# --- Constants and Configuration ---

MAX_LIMIT = 100
VALID_SEVERITIES = frozenset({'info', 'warning', 'error'})
DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}
PROJECTION_FIELDS = os.environ.get(
    'PROJECTION_FIELDS', 'id,severity,#datetime,message'
).split(',')
EXPRESSION_ATTRIBUTE_NAMES = {'#datetime': 'datetime'}


# --- Logging and Metrics ---

logger = Logger(service="LogQueryService")
metrics = Metrics(namespace="LogQueryService")


# --- Data Models ---

@dataclass
class QueryResult:
    """Container for query results with pagination support."""
    items: list
    has_more: bool
    next_token: Optional[str]


# --- DynamoDB Setup ---

TABLE_NAME = os.environ.get('TABLE_NAME')
if not TABLE_NAME:
    logger.error("Environment variable TABLE_NAME is required")
    raise RuntimeError("TABLE_NAME not configured")

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


# --- Helper Functions ---

def build_response(status_code: int, body: Dict) -> Dict:
    """Constructs an API Gateway compatible response.

    Args:
        status_code: HTTP status code
        body: Response body as a dictionary

    Returns:
        Dictionary with response structure
    """
    return {
        'statusCode': status_code,
        'headers': DEFAULT_HEADERS,
        'body': json.dumps(body, default=str, indent=2)
    }


def encode_start_key(start_key: Dict) -> str:
    """Encodes a DynamoDB start key for pagination tokens.

    Args:
        start_key: Dictionary representing DynamoDB start key

    Returns:
        Base64 encoded string safe for URL use
    """
    encoded = base64.urlsafe_b64encode(
        json.dumps(start_key).encode()
    )
    return encoded.decode()


def decode_start_key(encoded_key: str) -> Dict:
    """Decodes a pagination token back to a DynamoDB start key.

    Args:
        encoded_key: Base64 encoded start key

    Returns:
        Dictionary representing DynamoDB start key

    Raises:
        ValueError: If the token is invalid or malformed
    """
    try:
        decoded = base64.urlsafe_b64decode(encoded_key).decode()
        return json.loads(decoded)
    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Invalid pagination token: {e}")
        raise ValueError("Invalid pagination token")


def is_valid_start_key(start_key: Any, severity: Optional[str] = None) -> bool:
    """Validates the structure of a start key dictionary.

    Args:
        start_key: Potential start key to validate
        severity: If provided, validates as a severity index key

    Returns:
        True if the key has the required structure, False otherwise
    """
    if not isinstance(start_key, dict):
        return False
    required_keys = {'severity', 'datetime'} if severity else {'partition', 'datetime'}
    return all(key in start_key for key in required_keys)


def validate_projection_fields():
    """Logs warnings if projection fields aren't part of table schema."""
    try:
        response = dynamodb.meta.client.describe_table(TableName=TABLE_NAME)
        indexed_fields = {
            attr['AttributeName'] for attr in response['Table']['AttributeDefinitions']
        }
        projection_attributes = {
            field for field in PROJECTION_FIELDS
            if field not in EXPRESSION_ATTRIBUTE_NAMES
        }
        unindexed_fields = projection_attributes - indexed_fields
        if unindexed_fields:
            logger.warning(
                "Projection fields not in schema: "
                f"{unindexed_fields}"
            )
    except ClientError as e:
        logger.error(
            f"Failed to validate table schema: {e}"
        )


def validate_and_get_limit(query_params: Dict) -> Tuple[int, Optional[Dict]]:
    """Validates and extracts the limit parameter from query params.

    Args:
        query_params: Dictionary of query parameters

    Returns:
        Tuple of (validated limit, None) or (0, error response) if invalid
    """
    try:
        limit = min(int(query_params.get('limit', MAX_LIMIT)), MAX_LIMIT)
        if limit <= 0:
            raise ValueError("Limit must be positive")
        return limit, None
    except ValueError as e:
        return 0, build_response(400, {'error': str(e)})


def validate_and_get_start_key(query_params: Dict, severity: Optional[str]) -> Tuple[Optional[Dict], Optional[Dict]]:
    """Validates and decodes the start key/pagination token.

    Args:
        query_params: Dictionary of query parameters
        severity: Current severity filter if applicable

    Returns:
        Tuple of (start_key_dict, None) or (None, error_response) if invalid
    """
    if 'startKey' not in query_params or not query_params['startKey']:
        return None, None

    try:
        start_key = decode_start_key(query_params['startKey'])
        if not is_valid_start_key(start_key, severity):
            return None, build_response(
                400,
                {'error': 'Invalid pagination token structure'}
            )
        return start_key, None
    except ValueError as e:
        return None, build_response(400, {'error': str(e)})


def execute_query(
    index_name: str,
    key_condition,
    limit: int,
    start_key: Optional[Dict] = None
) -> QueryResult:
    """Executes a DynamoDB query and returns formatted results.

    Args:
        index_name: Name of the index to query
        key_condition: DynamoDB key condition expression
        limit: Maximum number of items to return
        start_key: Optional start key for pagination

    Returns:
        QueryResult containing items, pagination status, and next token

    Raises:
        ClientError: If the DynamoDB operation fails
    """
    params = {
        'IndexName': index_name,
        'KeyConditionExpression': key_condition,
        'ScanIndexForward': False,
        'Limit': limit,
        'ProjectionExpression': ','.join(PROJECTION_FIELDS),
        'ExpressionAttributeNames': EXPRESSION_ATTRIBUTE_NAMES
    }
    if start_key:
        params['ExclusiveStartKey'] = start_key

    start_time = time.time()
    try:
        response = table.query(**params)
        latency = (time.time() - start_time) * 1000
        metrics.add_metric(
            name=f"{index_name}QueryLatency",
            unit=MetricUnit.Milliseconds,
            value=latency
        )

        items = response.get('Items', [])
        last_key = response.get('LastEvaluatedKey')
        has_more = bool(last_key)
        next_token = encode_start_key(last_key) if has_more else None

        return QueryResult(items, has_more, next_token)
    except Exception as e:
        metrics.add_metric(
            name=f"{index_name}QueryErrors",
            unit=MetricUnit.Count,
            value=1
        )
        logger.error(f"Query failed on index {index_name}: {str(e)}")
        raise


# --- Main Handler ---

@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict, context: Any) -> Dict:
    """AWS Lambda handler for log query requests.

    Args:
        event: Lambda event containing request data
        context: Lambda execution context

    Returns:
        API Gateway formatted response
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        severity = query_params.get('severity', '').strip().lower()

        # Validate limit parameter
        limit, error_response = validate_and_get_limit(query_params)
        if error_response:
            return error_response

        # Validate start key if provided
        start_key, error_response = validate_and_get_start_key(query_params, severity)
        if error_response:
            return error_response

        logger.info(
            "Processing log request",
            extra={
                'severity': severity,
                'limit': limit,
                'has_start_key': bool(start_key)
            }
        )

        # Validate severity if provided
        if severity and severity not in VALID_SEVERITIES:
            return build_response(
                400,
                {
                    'error': (
                        f"Invalid severity. Must be one of "
                        f"{sorted(VALID_SEVERITIES)}"
                    )
                }
            )

        # Execute appropriate query based on severity filter
        if severity:
            result = execute_query(
                'severityindex',
                Key('severity').eq(severity),
                limit,
                start_key
            )
        else:
            result = execute_query(
                'alldatetimeindex',
                Key('partition').eq('ALL'),
                limit,
                start_key
            )

        # Format successful response
        response_body = {
            'items': result.items,
            'hasMore': result.has_more
        }
        if result.has_more:
            response_body['nextToken'] = result.next_token

        return build_response(200, response_body)

    except ClientError as e:
        logger.error(f"DynamoDB error: {e}", exc_info=True)
        metrics.add_metric(name="DynamoDBErrors", unit=MetricUnit.Count, value=1)
        return build_response(500, {'error': 'Database operation failed'})

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        metrics.add_metric(name="SystemErrors", unit=MetricUnit.Count, value=1)
        return build_response(500, {'error': 'Internal server error'})
