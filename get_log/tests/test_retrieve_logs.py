import os
import sys
import json
import base64
import pytest
from unittest.mock import MagicMock

# Patch sys.modules to avoid import errors from aws_lambda_powertools
sys.modules["aws_lambda_powertools"] = MagicMock()
sys.modules["aws_lambda_powertools.metrics"] = MagicMock()
sys.modules["aws_lambda_powertools.logging"] = MagicMock()

# Set required env vars before importing your module
os.environ["TABLE_NAME"] = "test-table"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"

from get_log import retrieve_logs as lambda_module  # noqa: E402


def make_start_key_token(start_key: dict):
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


@pytest.fixture(autouse=True)
def mock_dynamodb(monkeypatch):
    # Patch the DynamoDB Table resource
    mock_table = MagicMock()
    mock_resource = MagicMock()
    mock_resource.Table.return_value = mock_table
    monkeypatch.setattr(lambda_module, "table", mock_table)
    yield mock_table


def test_valid_query(monkeypatch, mock_dynamodb):
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "message": "test"}],
        "LastEvaluatedKey": None,
    }
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert not body.get("hasMore")


def test_invalid_limit(monkeypatch):
    event = {"queryStringParameters": {"limit": "-2"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]


def test_invalid_severity(monkeypatch):
    event = {"queryStringParameters": {"severity": "critical"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid severity" in response["body"]


def test_invalid_start_key(monkeypatch):
    event = {"queryStringParameters": {"startKey": "notbase64"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid or tampered pagination token" in response["body"]


def test_no_logs_found(monkeypatch, mock_dynamodb):
    mock_dynamodb.query.return_value = {"Items": []}
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["message"] == "No logs found"


def test_query_with_severity(monkeypatch, mock_dynamodb):
    mock_dynamodb.query.return_value = {
        "Items": [{"id": 1, "severity": "info", "message": "test"}],
        "LastEvaluatedKey": {
            "severity": "info",
            "datetime": "2024-01-01T00:00:00Z"
        },
    }
    event = {"queryStringParameters": {"severity": "info"}}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["hasMore"]
    assert "nextToken" in body


def test_dynamodb_client_error(monkeypatch, mock_dynamodb):
    mock_dynamodb.query.side_effect = lambda_module.ClientError(
        {"Error": {"Message": "fail"}},
        "query"
    )
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
    assert "Database operation failed" in response["body"]


def test_unexpected_exception(monkeypatch):
    monkeypatch.setattr(
        lambda_module,
        "execute_query",
        lambda *args, **kwargs: 1 / 0
    )
    event = {"queryStringParameters": None}
    response = lambda_module.lambda_handler(event, {})
    assert response["statusCode"] == 500
    assert "Internal server error" in response["body"]
