import sys
import json
import base64
import pytest
from unittest.mock import MagicMock
import boto3
from get_log.retrieve_logs import lambda_handler

# Mock AWS Lambda Powertools before any further imports
sys.modules["aws_lambda_powertools"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"].log_metrics = lambda func: func
sys.modules["aws_lambda_powertools.logging"] = MagicMock()
sys.modules["aws_lambda_powertools.logging"].logger = MagicMock()
sys.modules["aws_lambda_powertools.logging"].logger.inject_lambda_context = lambda func: func

# Mock boto3
boto3.resource = MagicMock()


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("PROJECTION_FIELDS", "id,severity,#datetime,message")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")


# Mock Lambda Context
class MockContext:
    function_name = "test-function"
    function_version = "$LATEST"
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    memory_limit_in_mb = 128
    aws_request_id = "test-request-id"
    log_group_name = "/aws/lambda/test-function"
    log_stream_name = "2023/01/01/[$LATEST]test-stream"


def make_start_key_token(start_key: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


@pytest.fixture(autouse=True)
def mock_dynamodb():
    mock_table = MagicMock()
    boto3.resource.return_value.Table.return_value = mock_table
    yield mock_table
    mock_table.reset_mock()


@pytest.fixture(autouse=True)
def mock_logger(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("get_log.retrieve_logs.logger", mock_logger)
    yield mock_logger


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

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert len(body["items"]) == 1


def test_invalid_limit_negative(mock_logger, lambda_context):
    event = {"queryStringParameters": {"limit": "-1"}}

    response = lambda_handler(event, lambda_context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called()


def test_invalid_severity(mock_logger, lambda_context):
    event = {"queryStringParameters": {"severity": "critical"}}

    response = lambda_handler(event, lambda_context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 400
    assert "Invalid severity" in response["body"]
    mock_logger.error.assert_called()


def test_pagination_continuation(mock_dynamodb, lambda_context):
    start_key = {"id": "last-item", "datetime": "2023-01-01"}
    token = make_start_key_token(start_key)

    mock_dynamodb.query.return_value = {
        "Items": [{"id": "2", "severity": "info", "message": "test2"}],
        "LastEvaluatedKey": None
    }

    event = {"queryStringParameters": {"startKey": token}}

    response = lambda_handler(event, lambda_context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["items"]) == 1


def test_dynamodb_error(mock_dynamodb, mock_logger, lambda_context):
    mock_dynamodb.query.side_effect = Exception("DynamoDB error")
    event = {"queryStringParameters": None}

    response = lambda_handler(event, lambda_context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 500
    mock_logger.error.assert_called()
