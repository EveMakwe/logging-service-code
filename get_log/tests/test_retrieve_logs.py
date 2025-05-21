import os
import pytest
import json
from unittest.mock import MagicMock, patch

# Set environment variables before importing the module
os.environ["TABLE_NAME"] = "TestTable"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"
os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "LogQueryService"
os.environ["POWERTOOLS_SERVICE_NAME"] = "LogQueryService"
os.environ["AWS_REGION"] = "us-west-2"
os.environ["VALIDATE_PROJECTION_FIELDS"] = "false"  # Disable validation during tests

# Mock the validate_projection_fields function before importing the module
with patch("get_log.retrieve_logs.validate_projection_fields"):
    import get_log.retrieve_logs as retrieve_logs  # noqa: E402


class LambdaContext:
    def __init__(self):
        self.function_name = "test-function"
        self.function_version = "$LATEST"
        self.invoked_function_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function"
        )
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
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("VALIDATE_PROJECTION_FIELDS", "false")
    yield


@pytest.fixture
def mock_table():
    mock_table = MagicMock()
    yield mock_table


@pytest.fixture
def lambda_context():
    return LambdaContext()


def test_lambda_handler_info_query(mock_table, lambda_context):
    mock_table.query.return_value = {
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

    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["severity"] == "info"


def test_lambda_handler_no_severity(mock_table, lambda_context):
    mock_table.query.return_value = {
        "Items": [
            {
                "id": "2",
                "severity": "warning",
                "datetime": "2024-01-02T00:00:00Z",
                "message": "Warning log",
            }
        ],
        "LastEvaluatedKey": None,
    }

    event = {"queryStringParameters": {"limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body


def test_lambda_handler_invalid_severity(mock_table, lambda_context):
    event = {"queryStringParameters": {"severity": "invalid"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_invalid_limit(mock_table, lambda_context):
    event = {"queryStringParameters": {"limit": "-5"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_no_items(mock_table, lambda_context):
    mock_table.query.return_value = {"Items": []}

    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["hasMore"] is False


def test_lambda_handler_with_pagination(mock_table, lambda_context):
    mock_table.query.return_value = {
        "Items": [
            {
                "id": "3",
                "severity": "error",
                "datetime": "2024-01-03T00:00:00Z",
                "message": "Error log",
            }
        ],
        "LastEvaluatedKey": {
            "severity": "error",
            "datetime": "2024-01-03T00:00:00Z",
            "id": "3",
        },
    }

    event = {"queryStringParameters": {"severity": "error", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["items"]) == 1
    assert body["hasMore"] is True
    assert "nextToken" in body


def test_lambda_handler_dynamodb_error(mock_table, lambda_context):
    mock_table.query.side_effect = Exception("DynamoDB error")

    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
