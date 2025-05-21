import os
import pytest
import json
from unittest.mock import patch, MagicMock

os.environ["TABLE_NAME"] = "TestTable"
os.environ["PROJECTION_FIELDS"] = "id,severity,#datetime,message"

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


def fake_table(*args, **kwargs):
    mock_table = MagicMock()
    mock_table.query.side_effect = fake_dynamodb_query
    return mock_table


# Note: patch 'get_log.retrieve_logs.get_table', not 'table'
@patch("get_log.retrieve_logs.get_table", new_callable=lambda: fake_table)
def test_lambda_handler_info_query(mock_get_table):
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["severity"] == "info"


@patch("get_log.retrieve_logs.get_table", new_callable=lambda: fake_table)
def test_lambda_handler_no_severity(mock_get_table):
    event = {"queryStringParameters": {"limit": "1"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "items" in body


@patch("get_log.retrieve_logs.get_table", new_callable=lambda: fake_table)
def test_lambda_handler_invalid_severity(mock_get_table):
    event = {"queryStringParameters": {"severity": "invalid"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


@patch("get_log.retrieve_logs.get_table", new_callable=lambda: fake_table)
def test_lambda_handler_invalid_limit(mock_get_table):
    event = {"queryStringParameters": {"limit": "-5"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


@patch("get_log.retrieve_logs.get_table", new_callable=lambda: fake_table)
def test_lambda_handler_no_items(mock_get_table):
    def no_items_query(**kwargs):
        return {"Items": []}

    table = fake_table()
    table.query.side_effect = no_items_query
    mock_get_table.return_value = table
    event = {"queryStringParameters": {"severity": "info", "limit": "1"}}
    context = {}
    response = retrieve_logs.lambda_handler(event, context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["hasMore"] is False
