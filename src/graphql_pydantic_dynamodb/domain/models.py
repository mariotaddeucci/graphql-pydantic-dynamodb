from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator
from ulid import ULID

_EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _new_ulid() -> str:
    return str(ULID())


class UserModel(BaseModel):
    user_id: str
    name: str
    email: str
    created_at: datetime


class PostModel(BaseModel):
    post_id: str
    author_id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class CommentModel(BaseModel):
    post_id: str
    comment_id: str
    author_id: str
    body: str
    created_at: datetime


class CreateUserInput(BaseModel):
    user_id: str = Field(default_factory=_new_ulid, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    email: str

    @field_validator("user_id", mode="before")
    @classmethod
    def default_user_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return str(_EMAIL_ADAPTER.validate_python(value))


class CreatePostInput(BaseModel):
    post_id: str = Field(default_factory=_new_ulid, min_length=1, max_length=128)
    author_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("post_id", mode="before")
    @classmethod
    def default_post_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()


class CreateCommentInput(BaseModel):
    post_id: str = Field(min_length=1, max_length=128)
    comment_id: str = Field(default_factory=_new_ulid, min_length=1, max_length=128)
    author_id: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1)

    @field_validator("comment_id", mode="before")
    @classmethod
    def default_comment_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()
