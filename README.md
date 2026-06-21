# graphql-pydantic-dynamodb

Projeto base completo com:

- **GraphQL** com `graphene` + `graphene-pydantic`
- **GraphiQL** no endpoint Lambda (`GET`) para exploração do schema
- **Modelagem tipada** com `pydantic`
- **Persistência no DynamoDB** com `dynantic`
- **Execução em AWS Lambda** via handler Python
- Estrutura padrão com `src/` e `test/`

## Estrutura

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
└── test_graphql_api.py
```

## Modelagem e relações (joins em nível de resolver)

- `User`
- `Post` (GSI por autor: `posts-by-author-index`)
- `Comment`

Os *joins* são resolvidos nos resolvers GraphQL:

- `User.posts`
- `Post.author`
- `Post.comments`
- `Comment.author`
- `Comment.post`

## Geração automática de queries e filtros

As queries de listagem agora aceitam `filters` gerados automaticamente a partir dos campos dos modelos Pydantic relacionados:

- `users(filters: UserFilterInput)`
- `posts(filters: PostFilterInput)`
- `comments(filters: CommentFilterInput)`
- `postsByAuthor(authorId: String!, filters: PostFilterInput)`
- `commentsByPost(postId: String!, filters: CommentFilterInput)`

Também foram adicionadas versões paginadas com token de cursor (`nextToken`):

- `usersPage(limit: Int, nextToken: String, filters: UserFilterInput)`
- `postsPage(limit: Int, nextToken: String, filters: PostFilterInput)`
- `commentsPage(limit: Int, nextToken: String, filters: CommentFilterInput)`
- `postsByAuthorPage(authorId: String!, limit: Int, nextToken: String, filters: PostFilterInput)`
- `commentsByPostPage(postId: String!, limit: Int, nextToken: String, filters: CommentFilterInput)`

Regras de geração de filtros:

- Campos escalares suportados geram `*_eq`
- Campos booleanos geram também `*_is`
- Campos `Literal`/`Enum` geram também `*_is_in`
- Campos de data (`date`/`datetime`) e numéricos (`int`/`float`) geram `*_eq`, `*_gte`, `*_gt`, `*_lte` e `*_lt`

Exemplo:

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

Exemplo com paginação por token:

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

## IDs automáticos com ULID

Os campos `user_id`, `post_id` e `comment_id` agora são gerados automaticamente com `python-ulid` quando não são enviados no input. Isso mantém os modelos Pydantic como fonte única para validação e para os tipos GraphQL (`graphene-pydantic`).

## Descrições dos modelos no schema GraphQL

As descrições dos modelos e campos agora são definidas diretamente nos modelos Pydantic (`Field(description=...)` e docstrings das classes). Essas descrições são expostas no schema GraphQL e ficam disponíveis via introspection para o frontend (incluindo o GraphiQL).

## Configuração via ambiente

Variáveis prefixadas com `APP_`:

- `APP_AWS_REGION` (default: `us-east-1`)
- `APP_DYNAMODB_ENDPOINT_URL` (opcional para localstack/dynamodb-local)
- `APP_USERS_TABLE` (default: `users`)
- `APP_POSTS_TABLE` (default: `posts`)
- `APP_COMMENTS_TABLE` (default: `comments`)
- `APP_POSTS_BY_AUTHOR_INDEX` (default: `posts-by-author-index`)

## Como rodar

1. Instalar dependências:

```bash
uv sync --dev
```

2. Executar testes:

```bash
uv run pytest
```

3. Exibir schema GraphQL (script do projeto):

```bash
uv run graphql-pydantic-dynamodb
```

4. Subir servidor local com GraphiQL:

```bash
uv run python dev.py --reload
```

## Exemplo de payload para Lambda

```json
{
  "query": "query($id:String!){ user(userId:$id){ userId name posts { postId title } } }",
  "variables": { "id": "user-1" }
}
```

Handler de entrada:

```python
from graphql_pydantic_dynamodb.lambda_handler import handler
```

### GraphiQL no Lambda

Com a mesma função Lambda:

- `GET /graphql` retorna a interface GraphiQL
- `POST /graphql` executa queries/mutations GraphQL
