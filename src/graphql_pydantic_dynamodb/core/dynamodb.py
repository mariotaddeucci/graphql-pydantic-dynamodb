from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient

from graphql_pydantic_dynamodb.core.settings import get_settings
from graphql_pydantic_dynamodb.persistence.models import CommentRecord, PostRecord, UserRecord


def build_dynamodb_client() -> BaseClient:
    settings = get_settings()
    client_kwargs: dict[str, Any] = {"service_name": "dynamodb", "region_name": settings.aws_region}

    if settings.dynamodb_endpoint_url:
        client_kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    if settings.aws_access_key_id:
        client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_session_token:
        client_kwargs["aws_session_token"] = settings.aws_session_token

    return boto3.client(**client_kwargs)


def configure_dynantic_client(client: BaseClient | None = None) -> BaseClient:
    dynamodb_client = client or build_dynamodb_client()
    for model in (UserRecord, PostRecord, CommentRecord):
        model.set_client(dynamodb_client)
    return dynamodb_client


@lru_cache(maxsize=1)
def get_dynamodb_client() -> BaseClient:
    return configure_dynantic_client()


def reset_dynamodb_client_cache() -> None:
    get_dynamodb_client.cache_clear()
