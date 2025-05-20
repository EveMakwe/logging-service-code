import os
import sys
import json
import base64
import pytest
from unittest.mock import MagicMock


# Patching and env setup must happen BEFORE importing the Lambda module
def dummy_log_metrics(*args, **kwargs):
    def decorator(func):
        def wrapper(*f_args, **f_kwargs):
            return func(*f_args, **f_kwargs)
        return wrapper
    return decorator


# Mock AWS Lambda Powertools before imports
sys.modules["aws_lambda_powertools"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"].log_metrics = dummy_log_metrics
sys.modules["aws_lambda_powertools.logging"] = MagicMock()

# Set environment variables
os.environ["TABLE_NAME"] = "test-table"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"
os.environ["AWS_REGION"] = "us-east-1"

# Import boto3 after mocks are set up
import boto3  # noqa: E402
boto3.resource = MagicMock()

# Import the module under test after all mocks are configured
from get_log import retrieve_logs as lambda_module  # noqa: E402


def make_start_key_token(start_key: dict) -> str:
    """Helper function to create a pagination token."""
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


@pytest.fixture(autouse=True)
def mock_dynamodb(monkeypatch):
    """Fixture to mock DynamoDB table."""
    mock_table = MagicMock()
    boto3.resource.return_value.Table.return_value = mock_table
    monkeypatch.setattr(lambda_module, "table", mock_table)
    yield mock_table
    mock_table.reset_mock()


@pytest.fixture(autouse=True)
def mock_logger(monkeypatch):
    """Fixture to mock the logger."""
    mock_logger = MagicMock()
    monkeypatch.setattr(lambda_module, "logger", mock_logger)
    yield mock_logger


def test_query_without_parameters(monkeypatch, mock_dynamodb):
    """Test query without any parameters."""
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": None,
    }
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert "hasMore" in body
    assert isinstance(body["items"], list)
    assert body["hasMore"] is False or body["hasMore"] is True


def test_invalid_limit_negative(monkeypatch, mock_logger):
    """Test with negative limit parameter."""
    event = {"queryStringParameters": {"limit": "-2"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called()


def test_invalid_limit_zero(monkeypatch, mock_logger):
    """Test with zero limit parameter."""
    event = {"queryStringParameters": {"limit": "0"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called()


def test_invalid_severity(monkeypatch, mock_logger):
    """Test with invalid severity parameter."""
    event = {"queryStringParameters": {"severity": "critical"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid severity" in response["body"]
    mock_logger.error.assert_called()


def test_invalid_start_key(monkeypatch, mock_logger):
    """Test with invalid start key parameter."""
    event = {"queryStringParameters": {"startKey": "notbase64"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid or tampered pagination token" in response["body"]
    mock_logger.error.assert_called()


def test_tampered_start_key(monkeypatch, mock_logger):
    """Test with tampered start key parameter."""
    tampered_token = make_start_key_token({"invalid": "key"})
    event = {"queryStringParameters": {"startKey": tampered_token}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] in (400, 500)


def test_no_logs_found(monkeypatch, mock_dynamodb):
    """Test when no logs are found."""
    mock_dynamodb.query.return_value = {"Items": [], "LastEvaluatedKey": None}
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body.get("message", "") == "No logs found" or "items" in body


def test_query_with_severity_and_pagination(monkeypatch, mock_dynamodb):
    """Test query with severity filter and pagination."""
    last_evaluated_key = {"severity": "info", "datetime": "2024-01-01T00:00:00Z"}
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": last_evaluated_key,
    }
    event = {"queryStringParameters": {"severity": "info", "limit": "10"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body and isinstance(body["items"], list)
    assert "nextToken" in body
    assert body["hasMore"]


def test_pagination_continuation(monkeypatch, mock_dynamodb):
    """Test pagination continuation with valid token."""
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
    assert "items" in body


def test_max_limit(monkeypatch, mock_dynamodb):
    """Test with maximum limit parameter."""
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": None,
    }
    event = {"queryStringParameters": {"limit": "1000"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body


def test_missing_query_parameters(monkeypatch, mock_dynamodb):
    """Test with missing query parameters."""
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test message"}],
        "LastEvaluatedKey": None,
    }
    event = {}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body


def test_missing_table_name(monkeypatch, mock_dynamodb, mock_logger):
    """Test when TABLE_NAME environment variable is missing."""
    monkeypatch.setenv("TABLE_NAME", "")
    monkeypatch.setattr(lambda_module, "table", None)
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500


def test_malformed_projection_fields(monkeypatch, mock_dynamodb, mock_logger):
    """Test with malformed PROJECTION_FIELDS environment variable."""
    monkeypatch.setenv("PROJECTION_FIELDS", "invalid_field,")
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500


def test_dynamodb_client_error(monkeypatch, mock_dynamodb, mock_logger):
    """Test when DynamoDB returns a client error."""
    mock_dynamodb.query.side_effect = lambda_module.ClientError(
        {"Error": {"Message": "DynamoDB failure"}}, "query"
    )
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500


def test_unexpected_exception(monkeypatch, mock_logger):
    """Test when an unexpected exception occurs."""
    monkeypatch.setattr(
        lambda_module,
        "execute_query",
        lambda *args, **kwargs: 1 / 0
    )
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
