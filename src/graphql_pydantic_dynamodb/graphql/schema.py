from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from types import UnionType
from typing import Any, Literal, Union, cast, get_args, get_origin

import graphene
from graphene_pydantic import PydanticInputObjectType, PydanticObjectType
from graphql import GraphQLError
from pydantic import BaseModel

from graphql_pydantic_dynamodb.domain.models import (
    CommentModel,
    CreateCommentInput,
    CreatePostInput,
    CreateUserInput,
    PostModel,
    UserModel,
)
from graphql_pydantic_dynamodb.services.blog_service import BlogService, get_default_service


def _to_mapping(input_value: Any) -> dict[str, Any]:
    if isinstance(input_value, dict):
        return input_value
    if hasattr(input_value, "items"):
        return dict(input_value.items())
    return {k: v for k, v in vars(input_value).items() if not k.startswith("_")}


def _to_input_type(model: type[BaseModel]) -> type[PydanticInputObjectType]:
    meta = type("Meta", (), {"model": model})
    attrs: dict[str, Any] = {"Meta": meta}
    if model.__doc__:
        attrs["__doc__"] = model.__doc__.strip()
    return cast(
        type[PydanticInputObjectType],
        type(f"{model.__name__}Type", (PydanticInputObjectType,), attrs),
    )


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin not in {UnionType, Union}:
        return annotation
    non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(non_none) != 1:
        return annotation
    return _unwrap_optional(non_none[0])


@lru_cache(maxsize=None)
def _to_graphene_enum(enum_type: type[Enum]) -> type[graphene.Enum]:
    return graphene.Enum.from_enum(enum_type)


def _is_enum(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, Enum)


def _is_literal(annotation: Any) -> bool:
    return get_origin(annotation) is Literal


def _literal_scalar(annotation: Any) -> Any | None:
    literal_values = get_args(annotation)
    if not literal_values:
        return None
    if all(isinstance(value, str) for value in literal_values):
        return graphene.String
    if all(isinstance(value, bool) for value in literal_values):
        return graphene.Boolean
    if all(isinstance(value, int) and not isinstance(value, bool) for value in literal_values):
        return graphene.Int
    return None


def _graphene_scalar(annotation: Any) -> Any | None:
    normalized = _unwrap_optional(annotation)
    if normalized is str:
        return graphene.String
    if normalized is int:
        return graphene.Int
    if normalized is float:
        return graphene.Float
    if normalized is bool:
        return graphene.Boolean
    if normalized is datetime:
        return graphene.DateTime
    if normalized is date:
        return graphene.Date
    if _is_enum(normalized):
        return _to_graphene_enum(normalized)
    if _is_literal(normalized):
        return _literal_scalar(normalized)
    return None


_FILTER_DESCRIPTIONS = {
    "eq": "Must equal the provided value.",
    "is": "Must match the provided boolean value.",
    "gte": "Must be greater than or equal to the provided value.",
    "gt": "Must be greater than the provided value.",
    "lte": "Must be less than or equal to the provided value.",
    "lt": "Must be less than the provided value.",
    "is_in": "Must be one of the provided values.",
}

_PAGINATION_LIMIT_DESCRIPTION = "Maximum number of items per page."
_PAGINATION_NEXT_TOKEN_ARGUMENT_DESCRIPTION = (
    "Token for the next page. Use the token returned in the previous response."
)
_PAGINATION_NEXT_TOKEN_FIELD_DESCRIPTION = (
    "Token for fetching the next page. Returns null when there are no more items."
)
_PAGINATION_FILTERS_DESCRIPTION = "Filters applied to the items on this page."


def _normalize_description(description: str | None, default: str) -> str:
    normalized = (description or default).strip()
    if not normalized.endswith("."):
        normalized = f"{normalized}."
    return normalized


def _compose_filter_description(base_description: str | None, op: str) -> str:
    description = _normalize_description(base_description, "Field value.")
    return f"{description} {_FILTER_DESCRIPTIONS[op]}"


def _compose_page_items_description(base_description: str | None) -> str:
    item_description = _normalize_description(base_description, "Item returned on the page.")
    return f"Items from the current page. {item_description}"


def _build_filter_fields(
    field_name: str,
    annotation: Any,
    field_description: str | None,
) -> dict[str, graphene.InputField]:
    scalar = _graphene_scalar(annotation)
    if scalar is None:
        return {}

    normalized = _unwrap_optional(annotation)
    fields = {
        f"{field_name}_eq": graphene.InputField(
            scalar,
            description=_compose_filter_description(field_description, "eq"),
        )
    }
    if normalized is bool:
        fields[f"{field_name}_is"] = graphene.InputField(
            graphene.Boolean,
            description=_compose_filter_description(field_description, "is"),
        )
    if normalized in {datetime, date, int, float}:
        fields[f"{field_name}_gte"] = graphene.InputField(
            scalar,
            description=_compose_filter_description(field_description, "gte"),
        )
        fields[f"{field_name}_gt"] = graphene.InputField(
            scalar,
            description=_compose_filter_description(field_description, "gt"),
        )
        fields[f"{field_name}_lte"] = graphene.InputField(
            scalar,
            description=_compose_filter_description(field_description, "lte"),
        )
        fields[f"{field_name}_lt"] = graphene.InputField(
            scalar,
            description=_compose_filter_description(field_description, "lt"),
        )
    if _is_enum(normalized) or _is_literal(normalized):
        fields[f"{field_name}_is_in"] = graphene.InputField(
            graphene.List(graphene.NonNull(scalar)),
            description=_compose_filter_description(field_description, "is_in"),
        )
    return fields


def _to_filter_input_type(model: type[BaseModel]) -> type[graphene.InputObjectType]:
    fields: dict[str, graphene.InputField] = {}
    for field_name, field_info in model.model_fields.items():
        fields.update(_build_filter_fields(field_name, field_info.annotation, field_info.description))

    type_name = f"{model.__name__.removesuffix('Model')}FilterInput"
    return cast(type[graphene.InputObjectType], type(type_name, (graphene.InputObjectType,), fields))


def _get_service(info: graphene.ResolveInfo) -> BlogService:
    context = info.context
    if isinstance(context, dict) and isinstance(context.get("service"), BlogService):
        return context["service"]
    if hasattr(context, "service") and isinstance(context.service, BlogService):
        return context.service
    return get_default_service()


class UserType(PydanticObjectType):
    posts = graphene.List(
        lambda: PostType,
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(lambda: PostFilterInputType),
    )

    class Meta:
        model = UserModel

    @staticmethod
    def resolve_posts(
        parent: UserModel,
        info: graphene.ResolveInfo,
        limit: int = 20,
        filters: Any = None,
    ) -> list[PostModel]:
        payload_filters = _to_mapping(filters) if filters is not None else None
        return _get_service(info).list_posts_by_author(parent.user_id, limit=limit, filters=payload_filters)


class PostType(PydanticObjectType):
    author = graphene.Field(UserType)
    comments = graphene.List(
        lambda: CommentType,
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(lambda: CommentFilterInputType),
    )

    class Meta:
        model = PostModel

    @staticmethod
    def resolve_author(parent: PostModel, info: graphene.ResolveInfo) -> UserModel | None:
        return _get_service(info).get_user(parent.author_id)

    @staticmethod
    def resolve_comments(
        parent: PostModel,
        info: graphene.ResolveInfo,
        limit: int = 20,
        filters: Any = None,
    ) -> list[CommentModel]:
        payload_filters = _to_mapping(filters) if filters is not None else None
        return _get_service(info).list_comments_by_post(parent.post_id, limit=limit, filters=payload_filters)


class CommentType(PydanticObjectType):
    author = graphene.Field(UserType)
    post = graphene.Field(PostType)

    class Meta:
        model = CommentModel

    @staticmethod
    def resolve_author(parent: CommentModel, info: graphene.ResolveInfo) -> UserModel | None:
        return _get_service(info).get_user(parent.author_id)

    @staticmethod
    def resolve_post(parent: CommentModel, info: graphene.ResolveInfo) -> PostModel | None:
        return _get_service(info).get_post(parent.post_id)


class UserPageType(graphene.ObjectType):
    items = graphene.List(
        UserType,
        required=True,
        description=_compose_page_items_description(UserModel.__doc__),
    )
    next_token = graphene.String(description=_PAGINATION_NEXT_TOKEN_FIELD_DESCRIPTION)


class PostPageType(graphene.ObjectType):
    items = graphene.List(
        PostType,
        required=True,
        description=_compose_page_items_description(PostModel.__doc__),
    )
    next_token = graphene.String(description=_PAGINATION_NEXT_TOKEN_FIELD_DESCRIPTION)


class CommentPageType(graphene.ObjectType):
    items = graphene.List(
        CommentType,
        required=True,
        description=_compose_page_items_description(CommentModel.__doc__),
    )
    next_token = graphene.String(description=_PAGINATION_NEXT_TOKEN_FIELD_DESCRIPTION)


CreateUserInputType = _to_input_type(CreateUserInput)
CreatePostInputType = _to_input_type(CreatePostInput)
CreateCommentInputType = _to_input_type(CreateCommentInput)
UserFilterInputType = _to_filter_input_type(UserModel)
PostFilterInputType = _to_filter_input_type(PostModel)
CommentFilterInputType = _to_filter_input_type(CommentModel)


class CreateUser(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(CreateUserInputType, required=True)

    Output = UserType

    @staticmethod
    def mutate(root: Any, info: graphene.ResolveInfo, input: Any) -> UserModel:
        payload = CreateUserInput.model_validate(_to_mapping(input))
        return _get_service(info).create_user(payload)


class CreatePost(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(CreatePostInputType, required=True)

    Output = PostType

    @staticmethod
    def mutate(root: Any, info: graphene.ResolveInfo, input: Any) -> PostModel:
        payload = CreatePostInput.model_validate(_to_mapping(input))
        try:
            return _get_service(info).create_post(payload)
        except ValueError as exc:
            raise GraphQLError(str(exc)) from exc


class CreateComment(graphene.Mutation):
    class Arguments:
        input = graphene.Argument(CreateCommentInputType, required=True)

    Output = CommentType

    @staticmethod
    def mutate(root: Any, info: graphene.ResolveInfo, input: Any) -> CommentModel:
        payload = CreateCommentInput.model_validate(_to_mapping(input))
        try:
            return _get_service(info).create_comment(payload)
        except ValueError as exc:
            raise GraphQLError(str(exc)) from exc


def _build_list_resolver(service_method: str, required_fields: tuple[str, ...] = ()) -> Any:
    def resolver(
        root: Any,
        info: graphene.ResolveInfo,
        limit: int = 20,
        filters: Any = None,
        **kwargs: Any,
    ) -> Any:
        payload_filters = _to_mapping(filters) if filters is not None else None
        resolver_kwargs: dict[str, Any] = {"limit": limit, "filters": payload_filters}
        for field_name in required_fields:
            resolver_kwargs[field_name] = kwargs[field_name]
        return getattr(_get_service(info), service_method)(**resolver_kwargs)

    return staticmethod(resolver)


def _build_page_resolver(service_method: str, required_fields: tuple[str, ...] = ()) -> Any:
    def resolver(
        root: Any,
        info: graphene.ResolveInfo,
        limit: int = 20,
        next_token: str | None = None,
        filters: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload_filters = _to_mapping(filters) if filters is not None else None
        resolver_kwargs: dict[str, Any] = {
            "limit": limit,
            "next_token": next_token,
            "filters": payload_filters,
        }
        for field_name in required_fields:
            resolver_kwargs[field_name] = kwargs[field_name]
        page = getattr(_get_service(info), service_method)(**resolver_kwargs)
        return {"items": page.items, "next_token": page.next_token}

    return staticmethod(resolver)


class Query(graphene.ObjectType):
    user = graphene.Field(UserType, user_id=graphene.String(required=True))
    users = graphene.List(
        UserType,
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(UserFilterInputType),
    )
    post = graphene.Field(PostType, post_id=graphene.String(required=True))
    posts = graphene.List(
        PostType,
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(PostFilterInputType),
    )
    comments = graphene.List(
        CommentType,
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(CommentFilterInputType),
    )
    posts_by_author = graphene.List(
        PostType,
        author_id=graphene.String(required=True),
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(PostFilterInputType),
    )
    comments_by_post = graphene.List(
        CommentType,
        post_id=graphene.String(required=True),
        limit=graphene.Int(default_value=20),
        filters=graphene.Argument(CommentFilterInputType),
    )
    users_page = graphene.Field(
        UserPageType,
        limit=graphene.Int(default_value=20, description=_PAGINATION_LIMIT_DESCRIPTION),
        next_token=graphene.String(description=_PAGINATION_NEXT_TOKEN_ARGUMENT_DESCRIPTION),
        filters=graphene.Argument(UserFilterInputType, description=_PAGINATION_FILTERS_DESCRIPTION),
    )
    posts_page = graphene.Field(
        PostPageType,
        limit=graphene.Int(default_value=20, description=_PAGINATION_LIMIT_DESCRIPTION),
        next_token=graphene.String(description=_PAGINATION_NEXT_TOKEN_ARGUMENT_DESCRIPTION),
        filters=graphene.Argument(PostFilterInputType, description=_PAGINATION_FILTERS_DESCRIPTION),
    )
    comments_page = graphene.Field(
        CommentPageType,
        limit=graphene.Int(default_value=20, description=_PAGINATION_LIMIT_DESCRIPTION),
        next_token=graphene.String(description=_PAGINATION_NEXT_TOKEN_ARGUMENT_DESCRIPTION),
        filters=graphene.Argument(CommentFilterInputType, description=_PAGINATION_FILTERS_DESCRIPTION),
    )
    posts_by_author_page = graphene.Field(
        PostPageType,
        author_id=graphene.String(required=True),
        limit=graphene.Int(default_value=20, description=_PAGINATION_LIMIT_DESCRIPTION),
        next_token=graphene.String(description=_PAGINATION_NEXT_TOKEN_ARGUMENT_DESCRIPTION),
        filters=graphene.Argument(PostFilterInputType, description=_PAGINATION_FILTERS_DESCRIPTION),
    )
    comments_by_post_page = graphene.Field(
        CommentPageType,
        post_id=graphene.String(required=True),
        limit=graphene.Int(default_value=20, description=_PAGINATION_LIMIT_DESCRIPTION),
        next_token=graphene.String(description=_PAGINATION_NEXT_TOKEN_ARGUMENT_DESCRIPTION),
        filters=graphene.Argument(CommentFilterInputType, description=_PAGINATION_FILTERS_DESCRIPTION),
    )

    @staticmethod
    def resolve_user(root: Any, info: graphene.ResolveInfo, user_id: str) -> UserModel | None:
        return _get_service(info).get_user(user_id)

    @staticmethod
    def resolve_post(root: Any, info: graphene.ResolveInfo, post_id: str) -> PostModel | None:
        return _get_service(info).get_post(post_id)

    resolve_users = _build_list_resolver("list_users")
    resolve_posts = _build_list_resolver("list_posts")
    resolve_comments = _build_list_resolver("list_comments")
    resolve_posts_by_author = _build_list_resolver("list_posts_by_author", ("author_id",))
    resolve_comments_by_post = _build_list_resolver("list_comments_by_post", ("post_id",))
    resolve_users_page = _build_page_resolver("list_users_page")
    resolve_posts_page = _build_page_resolver("list_posts_page")
    resolve_comments_page = _build_page_resolver("list_comments_page")
    resolve_posts_by_author_page = _build_page_resolver("list_posts_by_author_page", ("author_id",))
    resolve_comments_by_post_page = _build_page_resolver("list_comments_by_post_page", ("post_id",))


class Mutation(graphene.ObjectType):
    create_user = CreateUser.Field()
    create_post = CreatePost.Field()
    create_comment = CreateComment.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)


def execute_graphql(
    query: str,
    variables: dict[str, Any] | None = None,
    operation_name: str | None = None,
    service: BlogService | None = None,
) -> Any:
    context_service = service or get_default_service()
    return schema.execute(
        query,
        variable_values=variables,
        operation_name=operation_name,
        context_value={"service": context_service},
    )
