import os
import pytest
import json
from unittest.mock import patch, MagicMock

# Set environment variables before importing the module
os.environ["TABLE_NAME"] = "TestTable"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"
os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "LogQueryService"
os.environ["POWERTOOLS_SERVICE_NAME"] = "LogQueryService"

# Mock boto3 resource before importing retrieve_logs
with patch('boto3.resource') as mock_boto3:
    # Create a mock DynamoDB table
    mock_table = MagicMock()
    mock_boto3.return_value.Table.return_value = mock_table
    import get_log.retrieve_logs as retrieve_logs  # noqa: E402


class LambdaContext:
    def __init__(self):
        self.function_name = "test-function"
        self.function_version = "$LATEST"
        self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        self.memory_limit_in_mb = 128
        self.aws_request_id = "test-request-id"
        self.log_group_name = "/aws/lambda/test-function"
        self.log_stream_name = "2025/05/21/[$LATEST]test-stream"


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "TestTable")
    monkeypatch.setenv("PROJECTION_FIELDS", "id,severity,#datetime,message")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "LogQueryService")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "LogQueryService")
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


@pytest.fixture
def lambda_context():
    return LambdaContext()


def test_lambda_handler_info_query(mock_dynamodb, lambda_context):
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["severity"] == "info"


def test_lambda_handler_no_severity(mock_dynamodb, lambda_context):
    event = {"queryStringParameters": {"limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body


def test_lambda_handler_invalid_severity(mock_dynamodb, lambda_context):
    event = {"queryStringParameters": {"severity": "invalid"}}
    response = retrieve_logs.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_invalid_limit(mock_dynamodb, lambda_context):
    event = {"queryStringParameters": {"limit": "-5"}}
    response = retrieve_logs.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_no_items(mock_dynamodb, lambda_context):
    def no_items_query(**kwargs):
        return {"Items": []}

    mock_dynamodb.query.side_effect = no_items_query
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["hasMore"] is False
    