from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from graphql_pydantic_dynamodb.lambda_handler import handler  # noqa: E402

app = FastAPI(title="graphql-pydantic-dynamodb local dev")


def _to_api_gateway_event(request: Request, body: str | None = None) -> dict[str, Any]:
    method = request.method.upper()
    query_params = dict(request.query_params)
    if method == "GET":
        return {
            "requestContext": {"http": {"method": method}},
            "rawPath": request.url.path,
            "queryStringParameters": query_params or None,
        }
    return {
        "httpMethod": method,
        "path": request.url.path,
        "queryStringParameters": query_params or None,
        "isBase64Encoded": False,
        "body": body or "",
    }


def _from_lambda_response(lambda_response: dict[str, Any]) -> Response:
    status_code = int(lambda_response.get("statusCode", 200))
    headers = {
        key: value
        for key, value in lambda_response.get("headers", {}).items()
        if key.lower() != "content-length"
    }
    body = lambda_response.get("body", "")
    if not isinstance(body, str):
        body = json.dumps(body)
    return Response(content=body, status_code=status_code, headers=headers)


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/graphql")


@app.api_route("/graphql", methods=["GET", "POST"])
async def graphql(request: Request) -> Response:
    body = await request.body()
    event = _to_api_gateway_event(request=request, body=body.decode("utf-8"))
    return _from_lambda_response(handler(event, None))


def main() -> None:
    parser = argparse.ArgumentParser(description="Local FastAPI server for lambda_handler.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("dev:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
