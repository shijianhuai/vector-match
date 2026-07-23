import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

Role = Literal["owner", "editor", "viewer"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class DatasetCreateRequest(CamelModel):
    name: str = Field(min_length=1)
    description: str = ""


class DatasetUpdateRequest(CamelModel):
    id: uuid.UUID
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class DatasetResponse(CamelModel):
    id: uuid.UUID
    name: str
    description: str
    vector_model: str
    my_role: Role


class IdResponse(CamelModel):
    id: uuid.UUID | int


class DatasetMemberCreateRequest(CamelModel):
    username: str = Field(min_length=1)
    role: Role


class DatasetMemberUpdateRequest(CamelModel):
    role: Role


class DatasetMemberResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    user_id: int
    username: str
    role: Role


class RegisterRequest(CamelModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=6)
    email: str | None = Field(default=None, min_length=1)


class LoginRequest(CamelModel):
    username: str
    password: str


class UserResponse(CamelModel):
    id: int
    username: str
    email: str | None
    is_superuser: bool
    is_active: bool
    allow_api_key: bool
    create_time: datetime


class UserSearchItem(CamelModel):
    id: int
    username: str


class UserUpdateRequest(CamelModel):
    is_active: bool | None = None
    is_superuser: bool | None = None
    allow_api_key: bool | None = None


class UserListResponse(CamelModel):
    list: list[UserResponse]
    total: int


class LoginResponse(CamelModel):
    token: str
    user: UserResponse


class ApiKeyCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class ApiKeyUpdateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class ApiKeyResponse(CamelModel):
    id: int
    name: str
    key: str
    create_time: datetime
    last_used_at: datetime | None


class ApiKeyListResponse(CamelModel):
    list: list[ApiKeyResponse]
    total: int


class CollectionCreateRequest(CamelModel):
    dataset_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str = Field(min_length=1)
    type: Literal["folder", "virtual"]


class CollectionUpdateRequest(CamelModel):
    id: uuid.UUID
    name: str = Field(min_length=1)


class CollectionDeleteRequest(CamelModel):
    collection_ids: list[uuid.UUID] = Field(min_length=1)


class CollectionResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    type: str
    create_time: datetime
    update_time: datetime
    data_count: int | None = None

class CollectionListResponse(CamelModel):
    list: list[CollectionResponse]
    total: int


class IndexInput(CamelModel):
    text: str = Field(min_length=1)


class IndexResponse(CamelModel):
    type: str
    text: str


class PushDataItem(CamelModel):
    q: str = Field(min_length=1)
    a: str | None = None
    key_id: str | None = Field(None, min_length=1, max_length=128)
    updatetime: datetime | None = None
    indexes: list[IndexInput] = Field(default_factory=list, max_length=5)

    @field_validator("updatetime")
    @classmethod
    def _naive_to_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v

    @field_validator("updatetime")
    @classmethod
    def _updatetime_requires_key_id(cls, v: datetime | None, info) -> datetime | None:
        if v is not None and info.data.get("key_id") is None:
            raise ValueError("updatetime 必须配合 key_id 使用")
        return v


class PushDataRequest(CamelModel):
    collection_id: uuid.UUID
    data: list[PushDataItem] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _no_duplicate_key_ids(self):
        key_ids = [item.key_id for item in self.data if item.key_id]
        dup = {k for k in key_ids if key_ids.count(k) > 1}
        if dup:
            raise ValueError(f"批内 keyId 重复: {sorted(dup)}")
        return self


class PushDataResponse(CamelModel):
    insert_len: int
    update_len: int
    skip_len: int


class DataItemResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    q: str
    a: str | None
    trained: bool
    key_id: str | None


class DataListResponse(CamelModel):
    list: list[DataItemResponse]
    total: int


class DataDetailResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    q: str
    a: str | None
    trained: bool
    key_id: str | None
    source_updatetime: datetime | None
    indexes: list[IndexResponse]


class DataUpdateRequest(CamelModel):
    data_id: uuid.UUID
    q: str | None = Field(default=None, min_length=1)
    a: str | None = None
    indexes: list[IndexInput] | None = None


class DeleteByKeyRequest(CamelModel):
    collection_id: uuid.UUID
    key_ids: list[str] = Field(min_length=1, max_length=200)


class DeleteByKeyResponse(CamelModel):
    delete_len: int


class SearchRequest(CamelModel):
    dataset_id: uuid.UUID
    text: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    search_mode: Literal["embedding", "fullTextRecall", "mixedRecall"] = "embedding"
    using_re_rank: bool = False
    rerank_model: str | None = None


class SearchHitResponse(CamelModel):
    id: uuid.UUID
    q: str
    a: str | None
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    source_name: str
    score: float
    key_id: str | None
