import re

from graphql_pydantic_dynamodb.graphql.schema import execute_graphql
from graphql_pydantic_dynamodb.services.blog_service import BlogService

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
