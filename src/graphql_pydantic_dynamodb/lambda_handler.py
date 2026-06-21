import base64
import json
from typing import Any

from graphql_pydantic_dynamodb.graphql.schema import execute_graphql

_GRAPHIQL_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>GraphiQL</title>
    <style>
      html,
      body {
        margin: 0;
        height: 100vh;
      }
      #graphiql {
        height: 100vh;
      }
      .fallback {
        box-sizing: border-box;
        height: 100%;
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 16px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .fallback textarea {
        width: 100%;
        min-height: 180px;
        resize: vertical;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      .fallback button {
        width: fit-content;
        padding: 8px 12px;
        border-radius: 6px;
        border: 1px solid #ddd;
        background: #fafafa;
        cursor: pointer;
      }
      .fallback pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        background: #f6f8fa;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 12px;
      }
    </style>
  </head>
  <body>
    <div id="graphiql"></div>
    <script>
      (function () {
        const endpoint = "__GRAPHQL_ENDPOINT__";
        const root = document.getElementById("graphiql");

        function loadScriptWithFallback(urls) {
          return new Promise((resolve, reject) => {
            const tryLoad = (index) => {
              if (index >= urls.length) {
                reject(new Error("Could not load JS assets."));
                return;
              }
              const script = document.createElement("script");
              script.src = urls[index];
              script.crossOrigin = "anonymous";
              script.onload = resolve;
              script.onerror = () => tryLoad(index + 1);
              document.head.appendChild(script);
            };
            tryLoad(0);
          });
        }

        function loadStylesheetWithFallback(urls) {
          return new Promise((resolve, reject) => {
            const tryLoad = (index) => {
              if (index >= urls.length) {
                reject(new Error("Could not load CSS assets."));
                return;
              }
              const link = document.createElement("link");
              link.rel = "stylesheet";
              link.href = urls[index];
              link.onload = resolve;
              link.onerror = () => {
                link.remove();
                tryLoad(index + 1);
              };
              document.head.appendChild(link);
            };
            tryLoad(0);
          });
        }

        function renderFallback(errorMessage) {
          root.innerHTML = `
            <div class="fallback">
              <strong>GraphiQL failed to load.</strong>
              <div>${errorMessage}</div>
              <div>You can still run queries below:</div>
              <textarea id="fallback-query">query { __typename }</textarea>
              <textarea id="fallback-variables" placeholder='{"id":"123"}'></textarea>
              <button id="fallback-run">Execute</button>
              <pre id="fallback-result">Waiting for execution...</pre>
            </div>
          `;

          document.getElementById("fallback-run").addEventListener("click", async () => {
            const query = document.getElementById("fallback-query").value;
            const rawVariables = document.getElementById("fallback-variables").value.trim();
            const variables = rawVariables ? JSON.parse(rawVariables) : null;
            const resultEl = document.getElementById("fallback-result");
            try {
              const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, variables }),
              });
              const data = await response.json();
              resultEl.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
              resultEl.textContent = String(error);
            }
          });
        }

        async function boot() {
          try {
            await loadStylesheetWithFallback([
              "https://unpkg.com/graphiql@2.4.7/graphiql.min.css",
              "https://cdn.jsdelivr.net/npm/graphiql@2.4.7/graphiql.min.css"
            ]);
            await loadScriptWithFallback([
              "https://unpkg.com/react@18/umd/react.production.min.js",
              "https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js"
            ]);
            await loadScriptWithFallback([
              "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js",
              "https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js"
            ]);
            await loadScriptWithFallback([
              "https://unpkg.com/graphiql@2.4.7/graphiql.min.js",
              "https://cdn.jsdelivr.net/npm/graphiql@2.4.7/graphiql.min.js"
            ]);

            const fetcher = GraphiQL.createFetcher({ url: endpoint });
            ReactDOM.render(React.createElement(GraphiQL, { fetcher }), root);
          } catch (error) {
            renderFallback(String(error));
          }
        }

        boot();
      })();
    </script>
  </body>
</html>
"""


def _json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _html_response(status_code: int, body: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": body,
    }


def _http_method(event: dict[str, Any]) -> str:
    method = event.get("httpMethod")
    if isinstance(method, str):
        return method.upper()

    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        return "POST"

    http_context = request_context.get("http")
    if isinstance(http_context, dict) and isinstance(http_context.get("method"), str):
        return http_context["method"].upper()
    return "POST"


def _graphql_endpoint(event: dict[str, Any]) -> str:
    if isinstance(event.get("rawPath"), str):
        return event["rawPath"]
    if isinstance(event.get("path"), str):
        return event["path"]
    return "/graphql"


def _is_graphiql_request(event: dict[str, Any]) -> bool:
    if _http_method(event) != "GET":
        return False
    query_params = event.get("queryStringParameters")
    if not isinstance(query_params, dict):
        return True
    return not bool(query_params.get("query"))


def _render_graphiql(endpoint: str) -> str:
    return _GRAPHIQL_HTML_TEMPLATE.replace("__GRAPHQL_ENDPOINT__", endpoint)


def _parse_graphql_payload(event: dict[str, Any]) -> dict[str, Any]:
    if _http_method(event) == "GET":
        query_params = event.get("queryStringParameters")
        if not isinstance(query_params, dict):
            return {}
        variables = query_params.get("variables")
        parsed_variables = None
        if isinstance(variables, str) and variables:
            parsed_variables = json.loads(variables)
        elif isinstance(variables, dict):
            parsed_variables = variables
        return {
            "query": query_params.get("query"),
            "variables": parsed_variables,
            "operationName": query_params.get("operationName"),
        }

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

    if _is_graphiql_request(event):
        return _html_response(200, _render_graphiql(_graphql_endpoint(event)))

    try:
        payload = _parse_graphql_payload(event)
    except json.JSONDecodeError:
        return _json_response(400, {"errors": [{"message": "Invalid JSON payload."}]})

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
