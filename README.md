# graphql-pydantic-dynamodb

Complete base project with:

- **GraphQL** with `graphene` + `graphene-pydantic`
- **GraphiQL** on the Lambda endpoint (`GET`) for schema exploration
- **Typed models** with `pydantic`
- **DynamoDB persistence** with `dynantic`
- **AWS Lambda execution** via Python handler
- Standard structure with `src/` and `test/`

## Structure

```text
src/graphql_pydantic_dynamodb/
├── core/
│   ├── dynamodb.py
│   └── settings.py
├── domain/
│   └── models.py
├── graphql/
│   └── schema.py
├── persistence/
│   ├── models.py
│   └── repositories.py
├── services/
│   └── blog_service.py
└── lambda_handler.py

test/
├── conftest.py
├── test_graphql_api.py
└── test_lambda_handler.py
```

## Models and relationships (resolver-level joins)

- `User`
- `Post` (GSI by author: `posts-by-author-index`)
- `Comment`

*Joins* are resolved in the GraphQL resolvers:

- `User.posts`
- `Post.author`
- `Post.comments`
- `Comment.author`
- `Comment.post`

## Automatic query and filter generation

List queries now accept `filters` auto-generated from the fields of the related Pydantic models:

- `users(filters: UserFilterInput)`
- `posts(filters: PostFilterInput)`
- `comments(filters: CommentFilterInput)`
- `postsByAuthor(authorId: String!, filters: PostFilterInput)`
- `commentsByPost(postId: String!, filters: CommentFilterInput)`

Paginated versions with cursor token (`nextToken`) were also added:

- `usersPage(limit: Int, nextToken: String, filters: UserFilterInput)`
- `postsPage(limit: Int, nextToken: String, filters: PostFilterInput)`
- `commentsPage(limit: Int, nextToken: String, filters: CommentFilterInput)`
- `postsByAuthorPage(authorId: String!, limit: Int, nextToken: String, filters: PostFilterInput)`
- `commentsByPostPage(postId: String!, limit: Int, nextToken: String, filters: CommentFilterInput)`

Filter generation rules:

- Supported scalar fields generate `*_eq`
- Boolean fields also generate `*_is`
- `Literal`/`Enum` fields also generate `*_is_in`
- Date (`date`/`datetime`) and numeric (`int`/`float`) fields generate `*_eq`, `*_gte`, `*_gt`, `*_lte`, and `*_lt`

Example:

```graphql
query FilteredPosts($authorId: String!, $createdAt: DateTime!) {
  postsByAuthor(
    authorId: $authorId
    filters: { createdAtEq: $createdAt }
  ) {
    postId
    title
  }
}
```

Example with token-based pagination:

```graphql
query PaginatedPosts($authorId: String!, $nextToken: String) {
  postsByAuthorPage(authorId: $authorId, limit: 2, nextToken: $nextToken) {
    items {
      postId
      title
    }
    nextToken
  }
}
```

## Automatic IDs with ULID

The fields `user_id`, `post_id`, and `comment_id` are now auto-generated with `python-ulid` when not provided in the input. This keeps Pydantic models as the single source of truth for validation and GraphQL types (`graphene-pydantic`).

## Model descriptions in the GraphQL schema

Model and field descriptions are now defined directly in the Pydantic models (`Field(description=...)` and class docstrings). These descriptions are exposed in the GraphQL schema and available via introspection for the frontend (including GraphiQL).

In filters (`*FilterInput`), each operation also inherits the description from the original field and appends a simple operation phrase (e.g.: "Date and time when the post was created. Must be greater than the provided value.").

In pagination responses and arguments, simple descriptions were also added to the schema (`items`, `nextToken`, `limit`, and `filters`). The `items` field inherits the description from the paginated item model.

## Environment configuration

Variables prefixed with `APP_`:

- `APP_AWS_REGION` (default: `us-east-1`)
- `APP_DYNAMODB_ENDPOINT_URL` (optional for localstack/dynamodb-local)
- `APP_USERS_TABLE` (default: `users`)
- `APP_POSTS_TABLE` (default: `posts`)
- `APP_COMMENTS_TABLE` (default: `comments`)
- `APP_POSTS_BY_AUTHOR_INDEX` (default: `posts-by-author-index`)

## How to run

1. Install dependencies:

```bash
uv sync --dev
```

2. Run tests:

```bash
uv run pytest
```

3. Display GraphQL schema (project script):

```bash
uv run graphql-pydantic-dynamodb
```

4. Start local server with GraphiQL:

```bash
uv run python dev.py --reload
```

## Lambda payload example

```json
{
  "query": "query($id:String!){ user(userId:$id){ userId name posts { postId title } } }",
  "variables": { "id": "user-1" }
}
```

Entry handler:

```python
from graphql_pydantic_dynamodb.lambda_handler import handler
```

### GraphiQL on Lambda

With the same Lambda function:

- `GET /graphql` returns the GraphiQL interface
- `POST /graphql` executes GraphQL queries/mutations
