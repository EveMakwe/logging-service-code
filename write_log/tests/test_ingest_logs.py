import json
import os
import pytest
from write_log import ingest_logs

class MockTable:
    def __init__(self):
        self.saved_item = None

    def put_item(self, Item):
        self.saved_item = Item
        return {}

@pytest.fixture(autouse=True)
def set_table_env():
    os.environ["TABLE_NAME"] = "DummyTable"
    yield
    os.environ.pop("TABLE_NAME")

def test_lambda_handler_valid_log(monkeypatch):
    """Test a valid log entry is processed and saved."""

    # Arrange: Patch boto3 to use MockTable
    def mock_resource(service_name):
        class MockDynamoResource:
            def Table(self, name):
                return mock_table
        return MockDynamoResource()

    mock_table = MockTable()
    monkeypatch.setattr(ingest_logs.boto3, "resource", mock_resource)

    # Act: Build a valid event
    event = {
        "body": json.dumps({
            "severity": "info",
            "message": "Unit test log"
        })
    }
    result = ingest_logs.lambda_handler(event, None)

    # Assert: Status code, item was saved, correct severity and message
    assert result["statusCode"] == 201
    response_body = json.loads(result["body"])
    assert "id" in response_body
    assert mock_table.saved_item["severity"] == "info"
    assert mock_table.saved_item["message"] == "Unit test log"
