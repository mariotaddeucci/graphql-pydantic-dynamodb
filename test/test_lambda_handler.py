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

    assert user_type["description"] == "Represents a blog user."
    assert user_fields["userId"] == "Unique identifier for the user."
    assert user_fields["createdAt"] == "Date and time when the user was created."
    assert input_type["description"] == "Payload for creating a post."
    assert input_fields["postId"] == "Post identifier (ULID auto-generated when omitted)."
    assert input_fields["title"] == "Title of the post."
    assert filter_fields["createdAtGt"] == "Date and time when the post was created. Must be greater than the provided value."
    assert filter_fields["createdAtGte"] == "Date and time when the post was created. Must be greater than or equal to the provided value."
    assert filter_fields["createdAtLte"] == "Date and time when the post was created. Must be less than or equal to the provided value."
    assert post_page_fields["items"] == "Items from the current page. Represents a post created by a user."
    assert post_page_fields["nextToken"] == "Token for fetching the next page. Returns null when there are no more items."
    assert posts_by_author_page_args["limit"] == "Maximum number of items per page."
    assert (
        posts_by_author_page_args["nextToken"]
        == "Token for the next page. Use the token returned in the previous response."
    )
    assert posts_by_author_page_args["filters"] == "Filters applied to the items on this page."
