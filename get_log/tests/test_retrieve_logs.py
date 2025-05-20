import os
import sys
import json
import base64
import pytest
from unittest.mock import MagicMock

# ---- Patch Powertools decorators as passthroughs BEFORE importing the handler ----


def passthrough_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


# Patch modules and decorators
sys.modules["aws_lambda_powertools"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"].metrics_headers = passthrough_decorator
sys.modules["aws_lambda_powertools.metrics"].log_metrics = passthrough_decorator
sys.modules["aws_lambda_powertools.logging"] = MagicMock()
sys.modules["aws_lambda_powertools.logging"].logger = MagicMock()
sys.modules["aws_lambda_powertools.logging"].inject_lambda_context = passthrough_decorator

# ---- Set environment variables ----

os.environ.update({
    "TABLE_NAME": "test-table",
    "PROJECTION_FIELDS": "id,severity,#datetime,message",
    "AWS_REGION": "us-east-1"
})

import boto3  # noqa: E402
boto3.resource = MagicMock()

# ---- Import your lambda handler after patching ----

from get_log import retrieve_logs as lambda_module  # noqa: E402

# ---- Test utility functions ----


def make_start_key_token(start_key: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()

# ---- Pytest fixtures ----


@pytest.fixture(autouse=True)
def mock_dynamodb(monkeypatch):
    mock_table = MagicMock()
    boto3.resource.return_value.Table.return_value = mock_table
    monkeypatch.setattr(lambda_module, "table", mock_table)
    yield mock_table
    mock_table.reset_mock()


@pytest.fixture(autouse=True)
def mock_logger(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr(lambda_module, "logger", mock_logger)
    yield mock_logger

# ---- Tests ----


def test_query_without_parameters(mock_dynamodb):
    mock_dynamodb.query.return_value = {
        "Items": [{"id": "1", "severity": "info", "message": "test"}],
        "LastEvaluatedKey": None
    }
    event = {"queryStringParameters": None}
    context = {}

    # Call the actual decorated handler
    response = lambda_module.lambda_handler(event, context)

    # Ensure we got a real response, not a mock
    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "1"
    assert not body["hasMore"]


def test_invalid_limit_negative(mock_logger):
    event = {"queryStringParameters": {"limit": "-1"}}
    context = {}

    response = lambda_module.lambda_handler(event, context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called()


def test_invalid_severity(mock_logger):
    event = {"queryStringParameters": {"severity": "critical"}}
    context = {}

    response = lambda_module.lambda_handler(event, context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 400
    assert "Invalid severity" in response["body"]
    mock_logger.error.assert_called()


def test_pagination_continuation(mock_dynamodb):
    start_key = {"id": "last-item", "datetime": "2023-01-01"}
    token = make_start_key_token(start_key)

    mock_dynamodb.query.return_value = {
        "Items": [{"id": "2", "severity": "info", "message": "test2"}],
        "LastEvaluatedKey": None
    }

    event = {"queryStringParameters": {"startKey": token}}
    context = {}

    response = lambda_module.lambda_handler(event, context)

    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["items"]) == 1
    assert not body["hasMore"]


def test_dynamodb_error(mock_dynamodb, mock_logger):
    mock_dynamodb.query.side_effect = Exception("DynamoDB error")
    event = {"queryStringParameters": None}
    context = {}

    response = lambda_module.lambda_handler(event, context)
    assert not isinstance(response, MagicMock)
    assert response["statusCode"] == 500
    mock_logger.error.assert_called()
