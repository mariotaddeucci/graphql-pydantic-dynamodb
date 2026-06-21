from typing import Any

import boto3
import pytest
from moto import mock_aws

from graphql_pydantic_dynamodb.core.dynamodb import (
    configure_dynantic_client,
    reset_dynamodb_client_cache,
)
from graphql_pydantic_dynamodb.core.settings import get_settings, reset_settings_cache
from graphql_pydantic_dynamodb.services.blog_service import BlogService, reset_service_cache


def _create_tables(client: Any, settings: Any) -> None:
    client.create_table(
        TableName=settings.users_table,
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    client.create_table(
        TableName=settings.posts_table,
        KeySchema=[{"AttributeName": "post_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "post_id", "AttributeType": "S"},
            {"AttributeName": "author_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": settings.posts_by_author_index,
                "KeySchema": [
                    {"AttributeName": "author_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    client.create_table(
        TableName=settings.comments_table,
        KeySchema=[
            {"AttributeName": "post_id", "KeyType": "HASH"},
            {"AttributeName": "comment_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "post_id", "AttributeType": "S"},
            {"AttributeName": "comment_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture(autouse=True)
def fake_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("APP_AWS_REGION", "us-east-1")


@pytest.fixture
def blog_service() -> BlogService:
    reset_settings_cache()
    reset_dynamodb_client_cache()
    reset_service_cache()
    settings = get_settings()

    with mock_aws():
        client = boto3.client("dynamodb", region_name=settings.aws_region)
        _create_tables(client, settings)
        configure_dynantic_client(client)
        yield BlogService()

    reset_dynamodb_client_cache()
    reset_service_cache()
