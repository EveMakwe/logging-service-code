import json
import ingest_logs

def test_lambda_handler_valid_input(monkeypatch):
    # Mock DynamoDB put_item
    class MockTable:
        def put_item(self, Item):
            return {}

    monkeypatch.setattr(ingest_logs, "table", MockTable())

    event = {
        "body": json.dumps({
            "severity": "info",
            "message": "Test log"
        })
    }

    response = ingest_logs.lambda_handler(event, None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert "id" in body
    assert "datetime" in body
