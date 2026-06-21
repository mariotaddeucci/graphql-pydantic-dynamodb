# graphql-pydantic-dynamodb

Projeto base completo com:

- **GraphQL** com `graphene` + `graphene-pydantic`
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

## IDs automáticos com ULID

Os campos `user_id`, `post_id` e `comment_id` agora são gerados automaticamente com `python-ulid` quando não são enviados no input. Isso mantém os modelos Pydantic como fonte única para validação e para os tipos GraphQL (`graphene-pydantic`).

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
