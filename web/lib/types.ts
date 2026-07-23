export type AuthUser = {
  id: number;
  username: string;
  email: string | null;
  isSuperuser: boolean;
  allowApiKey: boolean;
};

export type Role = "owner" | "editor" | "viewer";

export type Dataset = {
  id: string;
  name: string;
  description: string | null;
  vectorModel: string | null;
  myRole: Role;
};

export type DatasetMember = {
  userId: number;
  username: string;
  role: Role;
};

export type User = {
  id: number;
  username: string;
  email: string | null;
  createTime: string;
  isActive: boolean;
  isSuperuser: boolean;
  allowApiKey: boolean;
};

export type ApiKey = {
  id: number;
  name: string;
  key: string;
  createTime: string;
  lastUsedAt: string | null;
};

export type CollectionType = "folder" | "virtual";

export type Collection = {
  id: string;
  datasetId: string;
  parentId: string | null;
  name: string;
  type: CollectionType;
  createTime: string;
  updateTime: string;
  dataCount?: number | null;
};

export type DataIndex = {
  type: string;
  text: string;
};

export type DataItem = {
  id: string;
  datasetId: string;
  collectionId: string;
  q: string;
  a: string | null;
  trained: boolean;
  keyId?: string | null;
};

export type DataDetail = DataItem & {
  sourceUpdatetime?: string | null;
  indexes: DataIndex[];
};

export type PushDataItem = {
  q: string;
  a?: string;
  keyId?: string;
  updatetime?: string;
  indexes?: { text: string }[];
};

export type PushDataRequest = {
  collectionId: string;
  data: PushDataItem[];
};

export type PushDataResponse = {
  insertLen: number;
  updateLen: number;
  skipLen: number;
};

export type IdResponse = {
  id: string;
};

export type ListResponse<T> = {
  list: T[];
  total: number;
};

export type SearchMode = "embedding" | "fullTextRecall" | "mixedRecall";

export type SearchRequest = {
  datasetId: string;
  text: string;
  topK?: number;
  similarity?: number;
  searchMode?: SearchMode;
  usingReRank?: boolean;
  rerankModel?: string;
};

export type SearchHit = {
  id: string;
  q: string;
  a: string | null;
  datasetId: string;
  collectionId: string;
  sourceName: string;
  score: number;
  keyId?: string | null;
};
