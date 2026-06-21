import json

from graphql_pydantic_dynamodb.lambda_handler import handler


def test_lambda_handler_serves_graphiql_on_get() -> None:
    event = {
        "requestContext": {"http": {"method": "GET"}},
        "rawPath": "/graphql",
    }

    response = handler(event, context=None)

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert "GraphiQL" in response["body"]
    assert "/graphql" in response["body"]


def test_lambda_handler_exposes_model_descriptions_in_introspection() -> None:
    query = """
    query IntrospectionDescriptions {
      userType: __type(name: "UserType") {
        description
        fields {
          name
          description
        }
      }
      createPostInputType: __type(name: "CreatePostInputType") {
        description
        inputFields {
          name
          description
        }
      }
      postFilterInputType: __type(name: "PostFilterInput") {
        inputFields {
          name
          description
        }
      }
      postPageType: __type(name: "PostPageType") {
        fields {
          name
          description
        }
      }
      queryType: __type(name: "Query") {
        fields {
          name
          args {
            name
            description
          }
        }
      }
    }
    """
    event = {"httpMethod": "POST", "body": json.dumps({"query": query})}

    response = handler(event, context=None)
    payload = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert "errors" not in payload

    user_type = payload["data"]["userType"]
    input_type = payload["data"]["createPostInputType"]
    filter_input_type = payload["data"]["postFilterInputType"]
    post_page_type = payload["data"]["postPageType"]
    query_type = payload["data"]["queryType"]
    user_fields = {field["name"]: field["description"] for field in user_type["fields"]}
    input_fields = {field["name"]: field["description"] for field in input_type["inputFields"]}
    filter_fields = {field["name"]: field["description"] for field in filter_input_type["inputFields"]}
    post_page_fields = {field["name"]: field["description"] for field in post_page_type["fields"]}
    query_fields = {field["name"]: field for field in query_type["fields"]}
    posts_by_author_page_args = {
        arg["name"]: arg["description"] for arg in query_fields["postsByAuthorPage"]["args"]
    }

    assert user_type["description"] == "Representa um usuário do blog."
    assert user_fields["userId"] == "Identificador único do usuário."
    assert user_fields["createdAt"] == "Data e hora de criação do usuário."
    assert input_type["description"] == "Payload para criação de publicação."
    assert input_fields["postId"] == "Identificador da publicação (ULID gerado automaticamente quando omitido)."
    assert input_fields["title"] == "Título da publicação."
    assert filter_fields["createdAtGt"] == "Data e hora de criação da publicação. Deve ser maior que o valor informado."
    assert filter_fields["createdAtGte"] == "Data e hora de criação da publicação. Deve ser maior ou igual ao valor informado."
    assert filter_fields["createdAtLte"] == "Data e hora de criação da publicação. Deve ser menor ou igual ao valor informado."
    assert post_page_fields["items"] == "Itens da página atual. Representa uma publicação criada por um usuário."
    assert post_page_fields["nextToken"] == "Token para buscar a próxima página. Retorna nulo quando não há mais itens."
    assert posts_by_author_page_args["limit"] == "Quantidade máxima de itens por página."
    assert (
        posts_by_author_page_args["nextToken"]
        == "Token da próxima página. Use o token retornado na resposta anterior."
    )
    assert posts_by_author_page_args["filters"] == "Filtros aplicados aos itens desta página."
