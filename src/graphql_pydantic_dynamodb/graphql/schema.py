from typing import Any

import graphene
from graphene_pydantic import PydanticInputObjectType, PydanticObjectType
from graphql import GraphQLError

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


def _get_service(info: graphene.ResolveInfo) -> BlogService:
    context = info.context
    if isinstance(context, dict) and isinstance(context.get("service"), BlogService):
        return context["service"]
    if hasattr(context, "service") and isinstance(context.service, BlogService):
        return context.service
    return get_default_service()


class UserType(PydanticObjectType):
    posts = graphene.List(lambda: PostType, limit=graphene.Int(default_value=20))

    class Meta:
        model = UserModel

    @staticmethod
    def resolve_posts(parent: UserModel, info: graphene.ResolveInfo, limit: int = 20) -> list[PostModel]:
        return _get_service(info).list_posts_by_author(parent.user_id, limit=limit)


class PostType(PydanticObjectType):
    author = graphene.Field(UserType)
    comments = graphene.List(lambda: CommentType, limit=graphene.Int(default_value=20))

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
    ) -> list[CommentModel]:
        return _get_service(info).list_comments_by_post(parent.post_id, limit=limit)


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


class CreateUserInputType(PydanticInputObjectType):
    class Meta:
        model = CreateUserInput


class CreatePostInputType(PydanticInputObjectType):
    class Meta:
        model = CreatePostInput


class CreateCommentInputType(PydanticInputObjectType):
    class Meta:
        model = CreateCommentInput


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


class Query(graphene.ObjectType):
    user = graphene.Field(UserType, user_id=graphene.String(required=True))
    users = graphene.List(UserType, limit=graphene.Int(default_value=20))
    post = graphene.Field(PostType, post_id=graphene.String(required=True))
    posts_by_author = graphene.List(
        PostType,
        author_id=graphene.String(required=True),
        limit=graphene.Int(default_value=20),
    )
    comments_by_post = graphene.List(
        CommentType,
        post_id=graphene.String(required=True),
        limit=graphene.Int(default_value=20),
    )

    @staticmethod
    def resolve_user(root: Any, info: graphene.ResolveInfo, user_id: str) -> UserModel | None:
        return _get_service(info).get_user(user_id)

    @staticmethod
    def resolve_users(root: Any, info: graphene.ResolveInfo, limit: int = 20) -> list[UserModel]:
        return _get_service(info).list_users(limit=limit)

    @staticmethod
    def resolve_post(root: Any, info: graphene.ResolveInfo, post_id: str) -> PostModel | None:
        return _get_service(info).get_post(post_id)

    @staticmethod
    def resolve_posts_by_author(
        root: Any,
        info: graphene.ResolveInfo,
        author_id: str,
        limit: int = 20,
    ) -> list[PostModel]:
        return _get_service(info).list_posts_by_author(author_id=author_id, limit=limit)

    @staticmethod
    def resolve_comments_by_post(
        root: Any,
        info: graphene.ResolveInfo,
        post_id: str,
        limit: int = 20,
    ) -> list[CommentModel]:
        return _get_service(info).list_comments_by_post(post_id=post_id, limit=limit)


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
