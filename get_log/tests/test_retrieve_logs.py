import os
import json
import base64
import pytest
from unittest.mock import MagicMock, patch


# Set up environment variables first
os.environ.update({
    "TABLE_NAME": "test-table",
    "PROJECTION_FIELDS": "id,severity,#datetime,message",
    "AWS_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing"
})


# Create a mock Lambda context
class MockContext:
    function_name = "test-function"
    function_version = "$LATEST"
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    memory_limit_in_mb = 128
    aws_request_id = "test-request-id"
    log_group_name = "/aws/lambda/test-function"
    log_stream_name = "2023/01/01/[$LATEST]test-stream"


# Mock AWS services before imports
with patch('boto3.resource') as mock_boto3_resource:
    mock_table = MagicMock()
    mock_boto3_resource.return_value.Table.return_value = mock_table

    # Mock Powertools logger
    with patch('aws_lambda_powertools.logging.logger') as mock_logger:
        mock_logger_instance = MagicMock()
        mock_logger.return_value = mock_logger_instance

        # Import the module under test
        from get_log.retrieve_logs import lambda_handler  # noqa: E402


def make_start_key_token(start_key: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


@pytest.fixture(autouse=True)
def mock_dynamodb():
    mock_table = MagicMock()
    with patch('boto3.resource') as mock_boto3_resource:
        mock_boto3_resource.return_value.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def lambda_context():
    return MockContext()


def test_query_without_parameters(mock_dynamodb, lambda_context):
    mock_dynamodb.query.return_value = {
        "Items": [{"id": "1", "severity": "info", "message": "test"}],
        "LastEvaluatedKey": None
    }
    event = {"queryStringParameters": None}

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "1"
    assert not body["hasMore"]


def test_invalid_limit_negative(mock_dynamodb, lambda_context):
    event = {"queryStringParameters": {"limit": "-1"}}

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]


def test_invalid_severity(mock_dynamodb, lambda_context):
    event = {"queryStringParameters": {"severity": "critical"}}

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    assert "Invalid severity" in response["body"]


def test_pagination_continuation(mock_dynamodb, lambda_context):
    start_key = {"id": "last-item", "datetime": "2023-01-01"}
    token = make_start_key_token(start_key)

    mock_dynamodb.query.return_value = {
        "Items": [{"id": "2", "severity": "info", "message": "test2"}],
        "LastEvaluatedKey": None
    }

    event = {"queryStringParameters": {"startKey": token}}

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["items"]) == 1
    assert not body["hasMore"]


def test_dynamodb_error(mock_dynamodb, lambda_context):
    mock_dynamodb.query.side_effect = Exception("DynamoDB error")
    event = {"queryStringParameters": None}

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 500
