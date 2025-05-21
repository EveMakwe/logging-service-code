import os
import pytest
import json
from unittest.mock import patch, MagicMock

# Set environment variables before importing the module
os.environ["TABLE_NAME"] = "TestTable"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"

# Mock boto3 resource before importing retrieve_logs
with patch('boto3.resource') as mock_boto3:
    # Create a mock DynamoDB table
    mock_table = MagicMock()
    mock_boto3.return_value.Table.return_value = mock_table
    import get_log.retrieve_logs as retrieve_logs  # noqa: E402


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "TestTable")
    monkeypatch.setenv("PROJECTION_FIELDS", "id,severity,#datetime,message")
    yield


def fake_dynamodb_query(**kwargs):
    return {
        "Items": [
            {
                "id": "1",
                "severity": "info",
                "datetime": "2024-01-01T00:00:00Z",
                "message": "Test log",
            }
        ],
        "LastEvaluatedKey": None,
    }


@pytest.fixture
def mock_dynamodb():
    with patch('get_log.retrieve_logs.table') as mock_table:
        mock_table.query.side_effect = fake_dynamodb_query
        yield mock_table


def test_lambda_handler_info_query(mock_dynamodb):
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["severity"] == "info"


def test_lambda_handler_no_severity(mock_dynamodb):
    event = {"queryStringParameters": {"limit": "1"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body


def test_lambda_handler_invalid_severity(mock_dynamodb):
    event = {"queryStringParameters": {"severity": "invalid"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_invalid_limit(mock_dynamodb):
    event = {"queryStringParameters": {"limit": "-5"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_no_items(mock_dynamodb):
    def no_items_query(**kwargs):
        return {"Items": []}

    mock_dynamodb.query.side_effect = no_items_query
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["hasMore"] is False
