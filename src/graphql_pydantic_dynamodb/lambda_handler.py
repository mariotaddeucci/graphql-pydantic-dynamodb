import base64
import json
from typing import Any

from graphql_pydantic_dynamodb.graphql.schema import execute_graphql


def _json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _parse_graphql_payload(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if body is None:
        return {}

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    if isinstance(body, str):
        return json.loads(body) if body else {}
    if isinstance(body, dict):
        return body
    return {}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context

    try:
        payload = _parse_graphql_payload(event)
    except json.JSONDecodeError:
        return _json_response(400, {"errors": [{"message": "Invalid JSON body."}]})

    query = payload.get("query")
    if not query:
        return _json_response(400, {"errors": [{"message": "Field 'query' is required."}]})

    result = execute_graphql(
        query=query,
        variables=payload.get("variables"),
        operation_name=payload.get("operationName"),
    )

    response_payload: dict[str, Any] = {"data": result.data}
    status_code = 200
    if result.errors:
        status_code = 400
        response_payload["errors"] = [error.formatted for error in result.errors]

    return _json_response(status_code, response_payload)
