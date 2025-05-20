import os
import json
import base64
import pytest
from unittest.mock import MagicMock, patch


# Set up environment variables first
os.environ.update({
    "TABLE_NAME": "test-table",
    "PROJECTION_FIELDS": "id,severity,#datetime,message",
    "AWS_REGION": "us-east-1"
})


# Mock boto3 and AWS services before importing the module
with patch('boto3.resource') as mock_boto3_resource:
    # Set up mock DynamoDB table
    mock_table = MagicMock()
    mock_boto3_resource.return_value.Table.return_value = mock_table

    # Import the module under test
    from get_log.retrieve_logs import lambda_handler as undecorated_handler  # noqa: E402


def make_start_key_token(start_key: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(start_key).encode()).decode()


@pytest.fixture(autouse=True)
def mock_dynamodb():
    mock_table = MagicMock()
    with patch('boto3.resource') as mock_boto3_resource:
        mock_boto3_resource.return_value.Table.return_value = mock_table
        yield mock_table


@pytest.fixture(autouse=True)
def mock_logger(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr('get_log.retrieve_logs.logger', mock_logger)
    yield mock_logger


def test_query_without_parameters(mock_dynamodb):
    mock_dynamodb.query.return_value = {
        "Items": [{"id": "1", "severity": "info", "message": "test"}],
        "LastEvaluatedKey": None
    }
    event = {"queryStringParameters": None}
    context = {}

    response = undecorated_handler(event, context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "1"
    assert not body["hasMore"]


def test_invalid_limit_negative(mock_logger):
    event = {"queryStringParameters": {"limit": "-1"}}
    context = {}

    response = undecorated_handler(event, context)

    assert response["statusCode"] == 400
    assert "Limit must be positive" in response["body"]
    mock_logger.error.assert_called()


def test_invalid_severity(mock_logger):
    event = {"queryStringParameters": {"severity": "critical"}}
    context = {}

    response = undecorated_handler(event, context)

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

    response = undecorated_handler(event, context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["items"]) == 1
    assert not body["hasMore"]


def test_dynamodb_error(mock_dynamodb, mock_logger):
    mock_dynamodb.query.side_effect = Exception("DynamoDB error")
    event = {"queryStringParameters": None}
    context = {}

    response = undecorated_handler(event, context)

    assert response["statusCode"] == 500
    mock_logger.error.assert_called()