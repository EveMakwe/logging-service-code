import pytest
import json
from unittest.mock import MagicMock, patch

# Patch before import to avoid side effects
with patch("get_log.retrieve_logs.validate_projection_fields"):
    import get_log.retrieve_logs as retrieve_logs


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


@pytest.fixture
def mock_table():
    return MagicMock()


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
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
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
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert "items" in body


@pytest.mark.parametrize(
    "event",
    [
        ({"queryStringParameters": {"severity": "invalid"}}),
        ({"queryStringParameters": {"limit": "-5"}}),
    ],
)
def test_lambda_handler_invalid_inputs(mock_table, lambda_context, event):
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)
    body = json.loads(response["body"])
    assert response["statusCode"] == 400
    assert "error" in body


def test_lambda_handler_no_items(mock_table, lambda_context):
    mock_table.query.return_value = {"Items": []}
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
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
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert len(body["items"]) == 1
    assert body["hasMore"] is True
    assert "nextToken" in body


def test_lambda_handler_dynamodb_error(mock_table, lambda_context):
    mock_table.query.side_effect = Exception("DynamoDB error")
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    response = retrieve_logs.lambda_handler(event, lambda_context, table=mock_table)
    body = json.loads(response["body"])
    assert response["statusCode"] == 500
    assert "error" in body
