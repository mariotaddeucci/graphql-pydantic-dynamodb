from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from dynantic import Attr
from pydantic import BaseModel

from graphql_pydantic_dynamodb.core.settings import get_settings
from graphql_pydantic_dynamodb.domain.models import (
    CommentModel,
    CreateCommentInput,
    CreatePostInput,
    CreateUserInput,
    PostModel,
    UserModel,
)
from graphql_pydantic_dynamodb.persistence.models import CommentRecord, PostRecord, UserRecord

ModelT = TypeVar("ModelT", bound=BaseModel)
_FILTER_SUFFIXES = ("_is_in", "_is", "_gte", "_gt", "_lte", "_lt", "_eq")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_model(model_type: type[ModelT], record: BaseModel) -> ModelT:
    return model_type.model_validate(record.model_dump(mode="python"))


def _to_user_model(record: UserRecord) -> UserModel:
    return _to_model(UserModel, record)


def _to_post_model(record: PostRecord) -> PostModel:
    return _to_model(PostModel, record)


def _to_comment_model(record: CommentRecord) -> CommentModel:
    return _to_model(CommentModel, record)


@dataclass(frozen=True)
class PageResult(Generic[ModelT]):
    items: list[ModelT]
    next_token: str | None


def _encode_next_token(offset: int) -> str:
    payload = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8")


def _decode_next_token(next_token: str | None) -> int:
    if next_token is None:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(next_token.encode("utf-8")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid pagination token.") from exc

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid pagination token.") from exc

    offset = payload.get("offset")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("Invalid pagination token.")
    return offset


def _paginate(items: list[ModelT], limit: int, next_token: str | None = None) -> PageResult[ModelT]:
    if limit < 1:
        raise ValueError("Limit must be greater than zero.")
    start = _decode_next_token(next_token)
    end = start + limit
    page_items = items[start:end]
    page_next_token = _encode_next_token(end) if end < len(items) else None
    return PageResult(items=page_items, next_token=page_next_token)


def _parse_filter_key(key: str) -> tuple[str, str]:
    for suffix in _FILTER_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)], suffix[1:]
    raise ValueError(f"Unsupported filter operator in '{key}'.")


def _matches_filter(value: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return value == expected
    if operator == "is":
        if not isinstance(expected, bool):
            raise ValueError("Filter 'is' requires a boolean value.")
        return value is expected
    if operator == "gte":
        return value >= expected
    if operator == "gt":
        return value > expected
    if operator == "lte":
        return value <= expected
    if operator == "lt":
        return value < expected
    if operator == "is_in":
        if not isinstance(expected, list):
            raise ValueError("Filter 'is_in' requires a list.")
        return value in expected
    raise ValueError(f"Unsupported filter operator '{operator}'.")


def _apply_filters(items: list[ModelT], filters: dict[str, Any] | None) -> list[ModelT]:
    if not filters:
        return items

    filtered_items: list[ModelT] = []
    for item in items:
        include_item = True
        for key, expected in filters.items():
            field_name, operator = _parse_filter_key(key)
            if not _matches_filter(getattr(item, field_name), operator, expected):
                include_item = False
                break
        if include_item:
            filtered_items.append(item)
    return filtered_items


class UserRepository:
    def create(self, payload: CreateUserInput) -> UserModel:
        record = UserRecord(
            user_id=payload.user_id,
            name=payload.name,
            email=str(payload.email),
            created_at=_utcnow(),
        )
        record.save(condition=Attr("user_id").not_exists())
        return _to_user_model(record)

    def get(self, user_id: str) -> UserModel | None:
        record = UserRecord.get(user_id)
        return _to_user_model(record) if record else None

    def list(self, limit: int = 20, filters: dict[str, Any] | None = None) -> list[UserModel]:
        return self.list_page(limit=limit, filters=filters).items

    def list_page(
        self,
        limit: int = 20,
        next_token: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> PageResult[UserModel]:
        builder = UserRecord.scan()
        users = [_to_user_model(record) for record in builder.all()]
        return _paginate(_apply_filters(users, filters), limit=limit, next_token=next_token)


class PostRepository:
    def create(self, payload: CreatePostInput) -> PostModel:
        record = PostRecord(
            post_id=payload.post_id,
            author_id=payload.author_id,
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            created_at=_utcnow(),
        )
        record.save(condition=Attr("post_id").not_exists())
        return _to_post_model(record)

    def get(self, post_id: str) -> PostModel | None:
        record = PostRecord.get(post_id)
        return _to_post_model(record) if record else None

    def list(self, limit: int = 20, filters: dict[str, Any] | None = None) -> list[PostModel]:
        return self.list_page(limit=limit, filters=filters).items

    def list_page(
        self,
        limit: int = 20,
        next_token: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> PageResult[PostModel]:
        builder = PostRecord.scan()
        posts = [_to_post_model(record) for record in builder.all()]
        return _paginate(_apply_filters(posts, filters), limit=limit, next_token=next_token)

    def list_by_author(
        self,
        author_id: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[PostModel]:
        return self.list_by_author_page(author_id, limit=limit, filters=filters).items

    def list_by_author_page(
        self,
        author_id: str,
        limit: int = 20,
        next_token: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> PageResult[PostModel]:
        settings = get_settings()
        builder = PostRecord.query_index(settings.posts_by_author_index, author_id).reverse()
        posts = [_to_post_model(record) for record in builder.all()]
        return _paginate(_apply_filters(posts, filters), limit=limit, next_token=next_token)


class CommentRepository:
    def create(self, payload: CreateCommentInput) -> CommentModel:
        record = CommentRecord(
            post_id=payload.post_id,
            comment_id=payload.comment_id,
            author_id=payload.author_id,
            body=payload.body,
            created_at=_utcnow(),
        )
        record.save(condition=Attr("comment_id").not_exists())
        return _to_comment_model(record)

    def list(self, limit: int = 20, filters: dict[str, Any] | None = None) -> list[CommentModel]:
        return self.list_page(limit=limit, filters=filters).items

    def list_page(
        self,
        limit: int = 20,
        next_token: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> PageResult[CommentModel]:
        builder = CommentRecord.scan()
        comments = [_to_comment_model(record) for record in builder.all()]
        return _paginate(_apply_filters(comments, filters), limit=limit, next_token=next_token)

    def list_by_post(
        self,
        post_id: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[CommentModel]:
        return self.list_by_post_page(post_id, limit=limit, filters=filters).items

    def list_by_post_page(
        self,
        post_id: str,
        limit: int = 20,
        next_token: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> PageResult[CommentModel]:
        builder = CommentRecord.query(post_id)
        comments = [_to_comment_model(record) for record in builder.all()]
        return _paginate(_apply_filters(comments, filters), limit=limit, next_token=next_token)
