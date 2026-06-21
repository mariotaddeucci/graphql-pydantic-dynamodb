from graphql_pydantic_dynamodb.graphql.schema import execute_graphql
from graphql_pydantic_dynamodb.services.blog_service import BlogService


def _assert_no_errors(result: object) -> None:
    assert result.errors is None, [error.formatted for error in result.errors]


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
        variables={
            "input": {"userId": "user-1", "name": "Alice", "email": "alice@example.com"}
        },
        service=blog_service,
    )
    _assert_no_errors(author)
    assert author.data["createUser"]["userId"] == "user-1"

    commenter = execute_graphql(
        query=create_user,
        variables={"input": {"userId": "user-2", "name": "Bob", "email": "bob@example.com"}},
        service=blog_service,
    )
    _assert_no_errors(commenter)
    assert commenter.data["createUser"]["userId"] == "user-2"

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
                "postId": "post-1",
                "authorId": "user-1",
                "title": "GraphQL na Lambda",
                "content": "Conteudo",
                "tags": ["serverless", "graphql"]
            }
        },
        service=blog_service,
    )
    _assert_no_errors(post)
    assert post.data["createPost"]["authorId"] == "user-1"

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
                "postId": "post-1",
                "commentId": "comment-1",
                "authorId": "user-2",
                "body": "Excelente artigo!"
            }
        },
        service=blog_service,
    )
    _assert_no_errors(comment)
    assert comment.data["createComment"]["commentId"] == "comment-1"

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
        variables={"postId": "post-1", "userId": "user-1"},
        service=blog_service,
    )
    _assert_no_errors(result)

    assert result.data["post"]["author"]["userId"] == "user-1"
    assert result.data["post"]["comments"][0]["author"]["userId"] == "user-2"
    assert result.data["user"]["posts"][0]["postId"] == "post-1"


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
                "postId": "post-x",
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
