import importlib
import re
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from graphql_pydantic_dynamodb.graphql.schema import execute_graphql
from graphql_pydantic_dynamodb.services.blog_service import BlogService

schema_module = importlib.import_module("graphql_pydantic_dynamodb.graphql.schema")

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _assert_no_errors(result: object) -> None:
    assert result.errors is None, [error.formatted for error in result.errors]


def _assert_ulid(value: str) -> None:
    assert _ULID_RE.fullmatch(value)


def test_graphql_creates_entities_and_resolves_relationships(blog_service: BlogService) -> None:
    create_user = """
    mutation CreateUser($input: CreateUserInputType!) {
      createUser(input: $input) {
        userId
        name
        email
      }
    }
    """

    author = execute_graphql(
        query=create_user,
        variables={"input": {"name": "Alice", "email": "alice@example.com"}},
        service=blog_service,
    )
    _assert_no_errors(author)
    author_id = author.data["createUser"]["userId"]
    _assert_ulid(author_id)

    commenter = execute_graphql(
        query=create_user,
        variables={"input": {"name": "Bob", "email": "bob@example.com"}},
        service=blog_service,
    )
    _assert_no_errors(commenter)
    commenter_id = commenter.data["createUser"]["userId"]
    _assert_ulid(commenter_id)

    create_post = """
    mutation CreatePost($input: CreatePostInputType!) {
      createPost(input: $input) {
        postId
        authorId
        title
        createdAt
      }
    }
    """
    post = execute_graphql(
        query=create_post,
        variables={
            "input": {
                "authorId": author_id,
                "title": "GraphQL na Lambda",
                "content": "Conteudo",
                "tags": ["serverless", "graphql"]
            }
        },
        service=blog_service,
    )
    _assert_no_errors(post)
    post_id = post.data["createPost"]["postId"]
    post_created_at = post.data["createPost"]["createdAt"]
    _assert_ulid(post_id)
    assert post.data["createPost"]["authorId"] == author_id

    create_comment = """
    mutation CreateComment($input: CreateCommentInputType!) {
      createComment(input: $input) {
        postId
        commentId
      }
    }
    """
    comment = execute_graphql(
        query=create_comment,
        variables={
            "input": {
                "postId": post_id,
                "authorId": commenter_id,
                "body": "Excelente artigo!"
            }
        },
        service=blog_service,
    )
    _assert_no_errors(comment)
    comment_id = comment.data["createComment"]["commentId"]
    _assert_ulid(comment_id)

    query = """
    query PostWithRelations($postId: String!, $userId: String!) {
      post(postId: $postId) {
        postId
        title
        author {
          userId
          name
        }
        comments {
          commentId
          body
          author {
            userId
            name
          }
        }
      }
      user(userId: $userId) {
        userId
        posts {
          postId
          title
        }
      }
    }
    """
    result = execute_graphql(
        query=query,
        variables={"postId": post_id, "userId": author_id},
        service=blog_service,
    )
    _assert_no_errors(result)

    assert result.data["post"]["author"]["userId"] == author_id
    assert result.data["post"]["comments"][0]["author"]["userId"] == commenter_id
    assert result.data["post"]["comments"][0]["commentId"] == comment_id
    assert result.data["user"]["posts"][0]["postId"] == post_id

    filters_query = """
    query FilteredPosts($authorId: String!, $createdAt: DateTime!) {
      postsByAuthor(
        authorId: $authorId
        filters: {createdAtEq: $createdAt}
      ) {
        postId
      }
      posts(
        filters: {
          authorIdEq: $authorId
          createdAtGte: $createdAt
          createdAtLte: $createdAt
        }
      ) {
        postId
      }
    }
    """
    filtered = execute_graphql(
        query=filters_query,
        variables={"authorId": author_id, "createdAt": post_created_at},
        service=blog_service,
    )
    _assert_no_errors(filtered)
    assert [post_item["postId"] for post_item in filtered.data["postsByAuthor"]] == [post_id]
    assert [post_item["postId"] for post_item in filtered.data["posts"]] == [post_id]


def test_graphql_rejects_post_without_existing_author(blog_service: BlogService) -> None:
    mutation = """
    mutation CreatePost($input: CreatePostInputType!) {
      createPost(input: $input) {
        postId
      }
    }
    """
    result = execute_graphql(
        query=mutation,
        variables={
            "input": {
                "authorId": "unknown-user",
                "title": "Nao deve criar",
                "content": "x",
                "tags": []
            }
        },
        service=blog_service,
    )

    assert result.errors is not None
    assert "Author 'unknown-user' was not found." in result.errors[0].message


def test_graphql_supports_pagination_with_next_token(blog_service: BlogService) -> None:
    create_user = """
    mutation CreateUser($input: CreateUserInputType!) {
      createUser(input: $input) {
        userId
      }
    }
    """
    user = execute_graphql(
        query=create_user,
        variables={"input": {"name": "Token User", "email": "token.user@example.com"}},
        service=blog_service,
    )
    _assert_no_errors(user)
    author_id = user.data["createUser"]["userId"]

    create_post = """
    mutation CreatePost($input: CreatePostInputType!) {
      createPost(input: $input) {
        postId
      }
    }
    """
    for index in range(3):
        created = execute_graphql(
            query=create_post,
            variables={
                "input": {
                    "authorId": author_id,
                    "title": f"Post {index}",
                    "content": "Conteudo",
                    "tags": [],
                }
            },
            service=blog_service,
        )
        _assert_no_errors(created)

    page_query = """
    query PostsByAuthorPage($authorId: String!, $nextToken: String) {
      postsByAuthorPage(authorId: $authorId, limit: 2, nextToken: $nextToken) {
        items {
          postId
        }
        nextToken
      }
    }
    """
    first_page = execute_graphql(
        query=page_query,
        variables={"authorId": author_id, "nextToken": None},
        service=blog_service,
    )
    _assert_no_errors(first_page)
    first_items = first_page.data["postsByAuthorPage"]["items"]
    next_token = first_page.data["postsByAuthorPage"]["nextToken"]
    assert len(first_items) == 2
    assert isinstance(next_token, str)

    second_page = execute_graphql(
        query=page_query,
        variables={"authorId": author_id, "nextToken": next_token},
        service=blog_service,
    )
    _assert_no_errors(second_page)
    second_items = second_page.data["postsByAuthorPage"]["items"]
    assert len(second_items) == 1
    assert second_page.data["postsByAuthorPage"]["nextToken"] is None

    combined_ids = [item["postId"] for item in first_items + second_items]
    assert len(combined_ids) == 3
    assert len(set(combined_ids)) == 3


def test_filter_input_generation_supports_enum_literal_and_date_ops() -> None:
    class StatusEnum(str, Enum):
        DRAFT = "DRAFT"
        PUBLISHED = "PUBLISHED"

    class SampleModel(BaseModel):
        status: StatusEnum
        visibility: Literal["public", "private"]
        published_at: datetime
        score: int
        featured: bool

    filter_input = schema_module._to_filter_input_type(SampleModel)

    assert "status_eq" in filter_input._meta.fields
    assert "status_is_in" in filter_input._meta.fields
    assert "visibility_eq" in filter_input._meta.fields
    assert "visibility_is_in" in filter_input._meta.fields
    assert "published_at_eq" in filter_input._meta.fields
    assert "published_at_gte" in filter_input._meta.fields
    assert "published_at_gt" in filter_input._meta.fields
    assert "published_at_lte" in filter_input._meta.fields
    assert "published_at_lt" in filter_input._meta.fields
    assert "score_eq" in filter_input._meta.fields
    assert "score_gte" in filter_input._meta.fields
    assert "score_gt" in filter_input._meta.fields
    assert "score_lte" in filter_input._meta.fields
    assert "score_lt" in filter_input._meta.fields
    assert "featured_eq" in filter_input._meta.fields
    assert "featured_is" in filter_input._meta.fields
