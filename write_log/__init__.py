import pytest
import json
import os
from botocore.exceptions import ClientError


@pytest.fixture(autouse=True)
def setup_env():
    os.environ["TABLE_NAME"] = "TestTable"
    yield
    os.environ.pop("TABLE_NAME", None)


class MockTable:
    def __init__(self):
        self.put_items = []

    def put_item(self, Item):
        self.put_items.append(Item)
        return {}

    def query(self, **kwargs):
        return {"Items": [], "LastEvaluatedKey": None}


class MockDynamoResource:
    def Table(self, name):
        return MockTable()


@pytest.fixture
def ingest_logs_handler(monkeypatch):
    import boto3
    monkeypatch.setattr(
        boto3,
        "resource",
        lambda x: MockDynamoResource()
    )
    from write_log import ingest_logs
    return ingest_logs


def test_write_valid_log(ingest_logs_handler, monkeypatch):
    mock_table = MockTable()
    monkeypatch.setattr(
        MockDynamoResource,
        "Table",
        lambda self, name: mock_table
    )
    event = {
        "body": json.dumps({
            "severity": "info",
            "message": "Test log"
        })
    }
    response = ingest_logs_handler.lambda_handler(event, None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert "id" in body
    assert len(mock_table.put_items) == 1
    assert mock_table.put_items[0]["severity"] == "info"
    assert mock_table.put_items[0]["message"] == "Test log"


def test_empty_input(ingest_logs_handler, monkeypatch):
    mock_table = MockTable()
    monkeypatch.setattr(
        MockDynamoResource,
        "Table",
        lambda self, name: mock_table
    )
    event = {"body": json.dumps({})}
    response = ingest_logs_handler.lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "Missing required fields" in body["error"]
    assert len(mock_table.put_items) == 0


def test_invalid_severity(ingest_logs_handler, monkeypatch):
    mock_table = MockTable()
    monkeypatch.setattr(
        MockDynamoResource,
        "Table",
        lambda self, name: mock_table
    )
    event = {
        "body": json.dumps({
            "severity": "critical",
            "message": "Test log"
        })
    }
    response = ingest_logs_handler.lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "Invalid severity" in body["error"]
    assert len(mock_table.put_items) == 0


def test_dynamodb_failure(ingest_logs_handler, monkeypatch):
    class FailingMockTable(MockTable):
        def put_item(self, Item):
            raise ClientError(
                {"Error": {"Code": "ResourceNotFoundException"}},
                "put_item"
            )
    monkeypatch.setattr(
        MockDynamoResource,
        "Table",
        lambda self, name: FailingMockTable()
    )
    event = {
        "body": json.dumps({
            "severity": "info",
            "message": "Test log"
        })
    }
    response = ingest_logs_handler.lambda_handler(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "Database operation failed" in body["error"]


def test_write_and_query_logs(ingest_logs_handler, monkeypatch):
    class QueryMockTable(MockTable):
        def query(self, **kwargs):
            return {
                "Items": [
                    {
                        "id": "1",
                        "severity": "info",
                        "datetime": "2025-05-18T12:00:00",
                        "message": "Test log"
                    }
                ],
                "LastEvaluatedKey": None
            }
    monkeypatch.setattr(
        MockDynamoResource,
        "Table",
        lambda self, name: QueryMockTable()
    )
    event = {
        "body": json.dumps({
            "severity": "info",
            "message": "Test log"
        })
    }
    response = ingest_logs_handler.lambda_handler(event, None)
    assert response["statusCode"] in [200, 201]
    body = json.loads(response["body"])
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["severity"] == "info"
    assert body["hasMore"] is False
