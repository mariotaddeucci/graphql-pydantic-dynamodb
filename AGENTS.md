# AGENTS.md

## Toolchain

- **Package manager**: `uv` (not pip/poetry). Python 3.12.
- `uv sync --dev` to install all deps.
- `uv run pytest` to run tests.

## Project commands

| Command | Purpose |
|---|---|
| `uv sync --dev` | Install deps (dev group includes fastapi, moto, pytest, uvicorn) |
| `uv run pytest` | Run all tests |
| `uv run pytest test/test_graphql_api.py` | Run only the GraphQL integration tests |
| `uv run graphql-pydantic-dynamodb` | Print the GraphQL schema to stdout |
| `uv run python dev.py --reload` | Start local FastAPI server wrapping the Lambda handler (GraphiQL at `/graphql`) |

There is **no lint, typecheck, or format command** configured. No ruff.toml, mypy.ini, or CI workflows exist.

## Architecture

Single package `graphql_pydantic_dynamodb` with layered structure:

```
domain/models.py     → Pydantic domain models + input payloads (source of truth for validation & descriptions)
persistence/models.py → Dynantic DynamoDB records (Key/SortKey/GSIKey annotations)
persistence/repositories.py → CRUD + client-side filtering & pagination
core/settings.py     → pydantic-settings (env prefix `APP_`), lru_cache
core/dynamodb.py     → boto3 client factory, Dynantic client wiring
services/blog_service.py → Orchestration (validates references before create)
graphql/schema.py    → graphene schema, types, queries, mutations, auto-generated filter inputs
lambda_handler.py    → AWS Lambda handler (API Gateway v1 + v2), includes built-in GraphiQL HTML
```

**Entry points**: `lambda_handler.handler` for Lambda, `dev.py` for local dev, `__init__.py` `main()` for schema printing.

## Caching & test fixtures

Several things use `@lru_cache(maxsize=1)`:
- `get_settings()` in `core/settings.py`
- `get_dynamodb_client()` in `core/dynamodb.py`
- `get_default_service()` in `services/blog_service.py`
- `_to_graphene_enum()` in `graphql/schema.py`

Tests that reconfigure settings or clients **must** call the matching `reset_*_cache()` functions. The `blog_service` fixture in `test/conftest.py` does this for you — use it for any test that hits DynamoDB.

The `fake_aws_credentials` fixture is `autouse=True` — all tests get fake AWS creds via monkeypatch.

## GraphQL schema conventions

- **Filter inputs** (`UserFilterInput`, etc.) are auto-generated from Pydantic model fields at module import time in `graphql/schema.py`. The generation logic (`_to_filter_input_type`, `_build_filter_fields`) introspects field annotations and creates `_eq`, `_gte`, `_gt`, `_lte`, `_lt`, `_is`, `_is_in` fields where applicable.
- **Descriptions** propagate from Pydantic `Field(description=...)` and class docstrings into the GraphQL schema via `graphene-pydantic`.
- **Context**: The schema passes `context_value={"service": blog_service}` to `schema.execute()`. The `_get_service()` helper extracts it from the resolver context. Tests pass `service=` to `execute_graphql()` directly.
- **`_to_mapping()`** converts graphene `InputObjectType` instances (which have `.items()`) or dicts into plain dicts for Pydantic validation.
- **ULID IDs** are auto-generated via `_new_ulid()` factory in `domain/models.py` when omitted from input. Validated by regex in tests (`^[0-9A-HJKMNP-TV-Z]{26}$`).

## DynamoDB / Dynantic patterns

- **Tables are created by the test fixture** (`_create_tables` in `conftest.py`), matching the Dynantic model annotations exactly.
- **Pagination is client-side**: scan/query fetches all items, then Python slices with base64-encoded cursor tokens.
- **Conditional writes**: `record.save(condition=Attr("pk").not_exists())` prevents overwrites.
- All `created_at` timestamps use `datetime.now(timezone.utc)`.
- Business rule: creating a post or comment validates the referenced author/post exists first, raising `ValueError` (caught and re-raised as `GraphQLError`).

## Resources referenced in README

The README contains extensive documentation on query patterns, filter rules, pagination, and model descriptions. It is accurate and should be treated as the primary reference for the GraphQL API surface.
