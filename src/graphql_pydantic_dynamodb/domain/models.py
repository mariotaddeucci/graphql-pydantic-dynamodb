from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator
from ulid import ULID

_EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _new_ulid() -> str:
    return str(ULID())


class UserModel(BaseModel):
    """Represents a blog user."""

    user_id: str = Field(description="Unique identifier for the user.")
    name: str = Field(description="Display name of the user.")
    email: str = Field(description="Email address of the user.")
    created_at: datetime = Field(description="Date and time when the user was created.")


class PostModel(BaseModel):
    """Represents a post created by a user."""

    post_id: str = Field(description="Unique identifier for the post.")
    author_id: str = Field(description="Identifier of the post author.")
    title: str = Field(description="Title of the post.")
    content: str = Field(description="Full content of the post.")
    tags: list[str] = Field(default_factory=list, description="List of tags associated with the post.")
    created_at: datetime = Field(description="Date and time when the post was created.")


class CommentModel(BaseModel):
    """Represents a comment associated with a post."""

    post_id: str = Field(description="Identifier of the post being commented on.")
    comment_id: str = Field(description="Unique identifier for the comment.")
    author_id: str = Field(description="Identifier of the comment author.")
    body: str = Field(description="Text of the comment.")
    created_at: datetime = Field(description="Date and time when the comment was created.")


class CreateUserInput(BaseModel):
    """Payload for creating a user."""

    user_id: str = Field(
        default_factory=_new_ulid,
        min_length=1,
        max_length=128,
        description="User identifier (ULID auto-generated when omitted).",
    )
    name: str = Field(min_length=1, max_length=120, description="Display name of the user.")
    email: str = Field(description="Valid email address of the user.")

    @field_validator("user_id", mode="before")
    @classmethod
    def default_user_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return str(_EMAIL_ADAPTER.validate_python(value))


class CreatePostInput(BaseModel):
    """Payload for creating a post."""

    post_id: str = Field(
        default_factory=_new_ulid,
        min_length=1,
        max_length=128,
        description="Post identifier (ULID auto-generated when omitted).",
    )
    author_id: str = Field(min_length=1, max_length=128, description="Identifier of the post author.")
    title: str = Field(min_length=1, max_length=200, description="Title of the post.")
    content: str = Field(min_length=1, description="Full content of the post.")
    tags: list[str] = Field(default_factory=list, description="List of tags associated with the post.")

    @field_validator("post_id", mode="before")
    @classmethod
    def default_post_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()


class CreateCommentInput(BaseModel):
    """Payload for creating a comment."""

    post_id: str = Field(min_length=1, max_length=128, description="Identifier of the post being commented on.")
    comment_id: str = Field(
        default_factory=_new_ulid,
        min_length=1,
        max_length=128,
        description="Comment identifier (ULID auto-generated when omitted).",
    )
    author_id: str = Field(min_length=1, max_length=128, description="Identifier of the comment author.")
    body: str = Field(min_length=1, description="Text of the comment.")

    @field_validator("comment_id", mode="before")
    @classmethod
    def default_comment_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()
