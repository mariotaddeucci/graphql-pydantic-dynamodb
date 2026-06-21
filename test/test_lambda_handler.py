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
    }
    """
    event = {"httpMethod": "POST", "body": json.dumps({"query": query})}

    response = handler(event, context=None)
    payload = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert "errors" not in payload

    user_type = payload["data"]["userType"]
    input_type = payload["data"]["createPostInputType"]
    user_fields = {field["name"]: field["description"] for field in user_type["fields"]}
    input_fields = {field["name"]: field["description"] for field in input_type["inputFields"]}

    assert user_type["description"] == "Representa um usuário do blog."
    assert user_fields["userId"] == "Identificador único do usuário."
    assert user_fields["createdAt"] == "Data e hora de criação do usuário."
    assert input_type["description"] == "Payload para criação de publicação."
    assert input_fields["postId"] == "Identificador da publicação (ULID gerado automaticamente quando omitido)."
    assert input_fields["title"] == "Título da publicação."
