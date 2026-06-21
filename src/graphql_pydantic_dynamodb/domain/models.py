from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator
from ulid import ULID

_EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _new_ulid() -> str:
    return str(ULID())


class UserModel(BaseModel):
    """Representa um usuário do blog."""

    user_id: str = Field(description="Identificador único do usuário.")
    name: str = Field(description="Nome de exibição do usuário.")
    email: str = Field(description="Endereço de e-mail do usuário.")
    created_at: datetime = Field(description="Data e hora de criação do usuário.")


class PostModel(BaseModel):
    """Representa uma publicação criada por um usuário."""

    post_id: str = Field(description="Identificador único da publicação.")
    author_id: str = Field(description="Identificador do autor da publicação.")
    title: str = Field(description="Título da publicação.")
    content: str = Field(description="Conteúdo completo da publicação.")
    tags: list[str] = Field(default_factory=list, description="Lista de tags associadas à publicação.")
    created_at: datetime = Field(description="Data e hora de criação da publicação.")


class CommentModel(BaseModel):
    """Representa um comentário associado a uma publicação."""

    post_id: str = Field(description="Identificador da publicação comentada.")
    comment_id: str = Field(description="Identificador único do comentário.")
    author_id: str = Field(description="Identificador do autor do comentário.")
    body: str = Field(description="Texto do comentário.")
    created_at: datetime = Field(description="Data e hora de criação do comentário.")


class CreateUserInput(BaseModel):
    """Payload para criação de usuário."""

    user_id: str = Field(
        default_factory=_new_ulid,
        min_length=1,
        max_length=128,
        description="Identificador do usuário (ULID gerado automaticamente quando omitido).",
    )
    name: str = Field(min_length=1, max_length=120, description="Nome de exibição do usuário.")
    email: str = Field(description="Endereço de e-mail válido do usuário.")

    @field_validator("user_id", mode="before")
    @classmethod
    def default_user_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return str(_EMAIL_ADAPTER.validate_python(value))


class CreatePostInput(BaseModel):
    """Payload para criação de publicação."""

    post_id: str = Field(
        default_factory=_new_ulid,
        min_length=1,
        max_length=128,
        description="Identificador da publicação (ULID gerado automaticamente quando omitido).",
    )
    author_id: str = Field(min_length=1, max_length=128, description="Identificador do autor da publicação.")
    title: str = Field(min_length=1, max_length=200, description="Título da publicação.")
    content: str = Field(min_length=1, description="Conteúdo completo da publicação.")
    tags: list[str] = Field(default_factory=list, description="Lista de tags associadas à publicação.")

    @field_validator("post_id", mode="before")
    @classmethod
    def default_post_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()


class CreateCommentInput(BaseModel):
    """Payload para criação de comentário."""

    post_id: str = Field(min_length=1, max_length=128, description="Identificador da publicação comentada.")
    comment_id: str = Field(
        default_factory=_new_ulid,
        min_length=1,
        max_length=128,
        description="Identificador do comentário (ULID gerado automaticamente quando omitido).",
    )
    author_id: str = Field(min_length=1, max_length=128, description="Identificador do autor do comentário.")
    body: str = Field(min_length=1, description="Texto do comentário.")

    @field_validator("comment_id", mode="before")
    @classmethod
    def default_comment_id(cls, value: str | None) -> str:
        return value if value is not None else _new_ulid()
