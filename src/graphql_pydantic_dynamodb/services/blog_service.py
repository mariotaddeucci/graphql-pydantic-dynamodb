from functools import lru_cache

from graphql_pydantic_dynamodb.core.dynamodb import get_dynamodb_client
from graphql_pydantic_dynamodb.domain.models import (
    CommentModel,
    CreateCommentInput,
    CreatePostInput,
    CreateUserInput,
    PostModel,
    UserModel,
)
from graphql_pydantic_dynamodb.persistence.repositories import (
    CommentRepository,
    PostRepository,
    UserRepository,
)


class BlogService:
    def __init__(
        self,
        users: UserRepository | None = None,
        posts: PostRepository | None = None,
        comments: CommentRepository | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.posts = posts or PostRepository()
        self.comments = comments or CommentRepository()

    def create_user(self, payload: CreateUserInput) -> UserModel:
        return self.users.create(payload)

    def get_user(self, user_id: str) -> UserModel | None:
        return self.users.get(user_id)

    def list_users(self, limit: int = 20) -> list[UserModel]:
        return self.users.list(limit=limit)

    def create_post(self, payload: CreatePostInput) -> PostModel:
        if self.get_user(payload.author_id) is None:
            raise ValueError(f"Author '{payload.author_id}' was not found.")
        return self.posts.create(payload)

    def get_post(self, post_id: str) -> PostModel | None:
        return self.posts.get(post_id)

    def list_posts_by_author(self, author_id: str, limit: int = 20) -> list[PostModel]:
        return self.posts.list_by_author(author_id=author_id, limit=limit)

    def create_comment(self, payload: CreateCommentInput) -> CommentModel:
        if self.get_user(payload.author_id) is None:
            raise ValueError(f"Author '{payload.author_id}' was not found.")
        if self.get_post(payload.post_id) is None:
            raise ValueError(f"Post '{payload.post_id}' was not found.")
        return self.comments.create(payload)

    def list_comments_by_post(self, post_id: str, limit: int = 20) -> list[CommentModel]:
        return self.comments.list_by_post(post_id=post_id, limit=limit)


@lru_cache(maxsize=1)
def get_default_service() -> BlogService:
    get_dynamodb_client()
    return BlogService()


def reset_service_cache() -> None:
    get_default_service.cache_clear()
