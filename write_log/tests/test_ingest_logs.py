import ingest_logs
import json


def test_lambda_handler_no_logs(monkeypatch):
    class MockTable:
        def query(self, **kwargs):
            return {"Items": []}

    monkeypatch.setattr(ingest_logs, "table", MockTable())

    event = {"queryStringParameters": {}}

    response = ingest_logs.lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["hasMore"] is False
