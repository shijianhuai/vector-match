import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


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


class IdResponse(CamelModel):
    id: uuid.UUID


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
    indexes: list[IndexInput] = Field(default_factory=list, max_length=5)


class PushDataRequest(CamelModel):
    collection_id: uuid.UUID
    data: list[PushDataItem] = Field(min_length=1, max_length=200)


class PushDataResponse(CamelModel):
    insert_len: int


class DataItemResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    q: str
    a: str | None
    trained: bool


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
    indexes: list[IndexResponse]


class DataUpdateRequest(CamelModel):
    data_id: uuid.UUID
    q: str | None = Field(default=None, min_length=1)
    a: str | None = None
    indexes: list[IndexInput] | None = None


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
