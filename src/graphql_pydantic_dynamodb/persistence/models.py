from datetime import datetime

from dynantic import DynamoModel, GSIKey, GSISortKey, Key, SortKey

from graphql_pydantic_dynamodb.core.settings import get_settings

_settings = get_settings()


class UserRecord(DynamoModel):
    user_id: str = Key()
    name: str
    email: str
    created_at: datetime

    class Meta:
        table_name = _settings.users_table


class PostRecord(DynamoModel):
    post_id: str = Key()
    author_id: str = GSIKey(index_name=_settings.posts_by_author_index)
    created_at: datetime = GSISortKey(index_name=_settings.posts_by_author_index)
    title: str
    content: str
    tags: list[str]

    class Meta:
        table_name = _settings.posts_table


class CommentRecord(DynamoModel):
    post_id: str = Key()
    comment_id: str = SortKey()
    author_id: str
    body: str
    created_at: datetime

    class Meta:
        table_name = _settings.comments_table
