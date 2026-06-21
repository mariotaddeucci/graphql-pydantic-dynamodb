from datetime import datetime, timezone
from typing import TypeVar

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

    def list(self, limit: int = 20) -> list[UserModel]:
        builder = UserRecord.scan().limit(limit)
        return [_to_user_model(record) for record in builder.all()]


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

    def list_by_author(self, author_id: str, limit: int = 20) -> list[PostModel]:
        settings = get_settings()
        builder = (
            PostRecord.query_index(settings.posts_by_author_index, author_id)
            .reverse()
            .limit(limit)
        )
        return [_to_post_model(record) for record in builder.all()]


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

    def list_by_post(self, post_id: str, limit: int = 20) -> list[CommentModel]:
        builder = CommentRecord.query(post_id).limit(limit)
        return [_to_comment_model(record) for record in builder.all()]
