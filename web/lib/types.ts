export type Dataset = {
  id: string;
  name: string;
  description: string | null;
  vectorModel: string | null;
};

export type CollectionType = "folder" | "virtual";

export type Collection = {
  id: string;
  datasetId: string;
  parentId: string | null;
  name: string;
  type: CollectionType;
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
};

export type DataDetail = DataItem & {
  indexes: DataIndex[];
};

export type PushDataItem = {
  q: string;
  a?: string;
  indexes?: { text: string }[];
};

export type PushDataRequest = {
  collectionId: string;
  data: PushDataItem[];
};

export type PushDataResponse = {
  insertLen: number;
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
};
