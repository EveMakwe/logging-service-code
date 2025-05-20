import os
import sys
import json
import base64
import pytest
from unittest.mock import MagicMock
import boto3

# Patch sys.modules for aws_lambda_powertools
sys.modules["aws_lambda_powertools"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"] = MagicMock()
sys.modules["aws_lambda_powertools.logging"] = MagicMock()

# Set environment variables
os.environ["TABLE_NAME"] = "test-table"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"
os.environ["AWS_REGION"] = "us-east-1"  # Fallback to avoid NoRegionError

# Mock boto3.resource before importing the module
boto3.resource = MagicMock()

# Import the module after mocking
from get_log import retrieve_logs as lambda_module  # noqa: E402


def make_start_key_token(start_key: dict) -> str:
    """Encode a start key dictionary into a base64 URL-safe string."""
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


@pytest.fixture(autouse=True)
def mock_dynamodb(monkeypatch):
    """Fixture to mock the DynamoDB table resource."""
    mock_table = MagicMock()
    boto3.resource.return_value.Table.return_value = mock_table
    monkeypatch.setattr(lambda_module, "table", mock_table)
    yield mock_table
    mock_table.reset_mock()


@pytest.fixture(autouse=True)
def mock_logger(monkeypatch):
    """Fixture to mock the aws_lambda_powertools logger."""
    mock_logger = MagicMock()
    monkeypatch.setattr(lambda_module, "logger", mock_logger)
    yield mock_logger


def test_query_without_parameters(monkeypatch, mock_dynamodb):
    """Test a successful query with no parameters, returning items and no pagination."""
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": None,
    }
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    expected_keys = {"items", "hasMore", "message"}
    assert set(body.keys()) == expected_keys
    assert body["items"] == [{"id": 1, "severity": "info", "message": "test message"}]
    assert body["hasMore"] is False
    assert body["message"] == "Logs retrieved successfully"
    mock_dynamodb.query.assert_called_once_with(
        ProjectionExpression="id,severity,#datetime,message",
        ExpressionAttributeNames={"#datetime": "datetime"},
    )


def test_invalid_limit_negative(monkeypatch, mock_logger):
    """Test handling of a negative limit parameter."""
    event = {"queryStringParameters": {"limit": "-2"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called_once()


def test_invalid_limit_zero(monkeypatch, mock_logger):
    """Test handling of a zero limit parameter."""
    event = {"queryStringParameters": {"limit": "0"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called_once()


def test_invalid_severity(monkeypatch, mock_logger):
    """Test handling of an invalid severity value."""
    event = {"queryStringParameters": {"severity": "critical"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid severity" in response["body"]
    mock_logger.error.assert_called_once()


def test_invalid_start_key(monkeypatch, mock_logger):
    """Test handling of an invalid (non-base64) startKey token."""
    event = {"queryStringParameters": {"startKey": "notbase64"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid or tampered pagination token" in response["body"]
    mock_logger.error.assert_called_once()


def test_tampered_start_key(monkeypatch, mock_logger):
    """Test handling of a tampered but valid base64 startKey token."""
    tampered_token = base64.urlsafe_b64encode(json.dumps({"invalid": "key"}).encode()).decode()
    event = {"queryStringParameters": {"startKey": tampered_token}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid or tampered pagination token" in response["body"]
    mock_logger.error.assert_called_once()


def test_no_logs_found(monkeypatch, mock_dynamodb):
    """Test handling when no logs are found."""
    mock_dynamodb.query.return_value = {"Items": [], "LastEvaluatedKey": None}
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    expected_keys = {"items", "hasMore", "message"}
    assert set(body.keys()) == expected_keys
    assert body["items"] == []
    assert body["hasMore"] is False
    assert body["message"] == "No logs found"


def test_query_with_severity_and_pagination(monkeypatch, mock_dynamodb):
    """Test querying logs with a valid severity filter and pagination."""
    last_evaluated_key = {"severity": "info", "datetime": "2024-01-01T00:00:00Z"}
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": last_evaluated_key,
    }
    event = {"queryStringParameters": {"severity": "info", "limit": "10"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    expected_keys = {"items", "hasMore", "nextToken", "message"}
    assert set(body.keys()) == expected_keys
    assert body["items"] == [{"id": 1, "severity": "info", "message": "test message"}]
    assert body["hasMore"] is True
    assert body["nextToken"] == make_start_key_token(last_evaluated_key)
    assert body["message"] == "Logs retrieved successfully"
    mock_dynamodb.query.assert_called_once_with(
        KeyConditionExpression="severity = :severity",
        ExpressionAttributeValues={":severity": "info"},
        ProjectionExpression="id,severity,#datetime,message",
        ExpressionAttributeNames={"#datetime": "datetime"},
        Limit=10,
    )


def test_pagination_continuation(monkeypatch, mock_dynamodb):
    """Test querying with a valid startKey for pagination continuation."""
    start_key = {"severity": "info", "datetime": "2024-01-01T00:00:00Z"}
    token = make_start_key_token(start_key)
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 2, "severity": "info", "message": "test message 2"}],
        "LastEvaluatedKey": None,
    }
    event = {"queryStringParameters": {"startKey": token, "severity": "info"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    expected_keys = {"items", "hasMore", "message"}
    assert set(body.keys()) == expected_keys
    assert body["items"] == [{"id": 2, "severity": "info", "message": "test message 2"}]
    assert body["hasMore"] is False
    mock_dynamodb.query.assert_called_once_with(
        KeyConditionExpression="severity = :severity",
        ExpressionAttributeValues={":severity": "info"},
        ProjectionExpression="id,severity,#datetime,message",
        ExpressionAttributeNames={"#datetime": "datetime"},
        ExclusiveStartKey=start_key,
    )


def test_max_limit(monkeypatch, mock_dynamodb):
    """Test handling of a large limit value."""
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": None,
    }
    event = {"queryStringParameters": {"limit": "1000"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    mock_dynamodb.query.assert_called_once_with(
        ProjectionExpression="id,severity,#datetime,message",
        ExpressionAttributeNames={"#datetime": "datetime"},
        Limit=1000,
    )


def test_missing_query_parameters(monkeypatch, mock_dynamodb):
    """Test handling of missing queryStringParameters."""
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": None,
    }
    event = {}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    expected_keys = {"items", "hasMore", "message"}
    assert set(body.keys()) == expected_keys
    assert body["items"] == [{"id": 1, "severity": "info", "message": "test message"}]
    assert body["hasMore"] is False


def test_missing_table_name(monkeypatch, mock_dynamodb, mock_logger):
    """Test handling of missing TABLE_NAME environment variable."""
    monkeypatch.setenv("TABLE_NAME", "")
    monkeypatch.setattr(lambda_module, "table", None)
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
    assert "Table name not configured" in response["body"]
    mock_logger.error.assert_called_once()


def test_malformed_projection_fields(monkeypatch, mock_dynamodb, mock_logger):
    """Test handling of malformed PROJECTION_FIELDS environment variable."""
    monkeypatch.setenv("PROJECTION_FIELDS", "invalid_field,")
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
    assert "Invalid projection fields configuration" in response["body"]
    mock_logger.error.assert_called_once()


def test_dynamodb_client_error(monkeypatch, mock_dynamodb, mock_logger):
    """Test handling of DynamoDB ClientError."""
    mock_dynamodb.query.side_effect = lambda_module.ClientError(
        {"Error": {"Message": "DynamoDB failure"}}, "query"
    )
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
    assert "Database operation failed" in response["body"]
    mock_logger.error.assert_called_once()


def test_unexpected_exception(monkeypatch, mock_logger):
    """Test handling of unexpected runtime errors."""
    monkeypatch.setattr(
        lambda_module,
        "execute_query",
        lambda *args, **kwargs: 1 / 0
    )
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
    assert "Internal server error" in response["body"]
    mock_logger.error.assert_called_once()
