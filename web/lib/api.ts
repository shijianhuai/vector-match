import type {
  Collection,
  DataDetail,
  DataItem,
  Dataset,
  IdResponse,
  ListResponse,
  PushDataRequest,
  PushDataResponse,
  SearchHit,
  SearchRequest,
} from "@/lib/types";

const baseUrl = "/api/proxy";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({} as { detail?: unknown }));
    const detail =
      typeof data.detail === "string" ? data.detail : data.detail ? JSON.stringify(data.detail) : null;
    throw new Error(detail || `请求失败：${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      sp.set(key, String(value));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export const datasetApi = {
  create: (payload: { name: string; description?: string }) =>
    fetchJson<IdResponse>("/create", { method: "POST", body: JSON.stringify(payload) }),
  list: () => fetchJson<Dataset[]>("/list"),
  detail: (id: string) => fetchJson<Dataset>(`/detail?id=${encodeURIComponent(id)}`),
  update: (payload: { id: string; name?: string; description?: string }) =>
    fetchJson<IdResponse>("/update", { method: "PUT", body: JSON.stringify(payload) }),
  delete: (id: string) =>
    fetchJson<IdResponse>(`/delete?id=${encodeURIComponent(id)}`, { method: "DELETE" }),
};

export const collectionApi = {
  create: (payload: {
    datasetId: string;
    parentId?: string;
    name: string;
    type: "folder" | "virtual";
  }) => fetchJson<IdResponse>("/collection/create", { method: "POST", body: JSON.stringify(payload) }),
  list: (params: {
    datasetId: string;
    parentId?: string;
    offset?: number;
    pageSize?: number;
    searchText?: string;
  }) => fetchJson<ListResponse<Collection>>(`/collection/list${buildQuery(params)}`),
  detail: (id: string) => fetchJson<Collection>(`/collection/detail?id=${encodeURIComponent(id)}`),
  update: (payload: { id: string; name: string }) =>
    fetchJson<IdResponse>("/collection/update", { method: "PUT", body: JSON.stringify(payload) }),
  delete: (collectionIds: string[]) =>
    fetchJson<IdResponse>("/collection/delete", {
      method: "DELETE",
      body: JSON.stringify({ collectionIds }),
    }),
};

export const dataApi = {
  push: (payload: PushDataRequest) =>
    fetchJson<PushDataResponse>("/data/pushData", { method: "POST", body: JSON.stringify(payload) }),
  list: (params: {
    collectionId: string;
    offset?: number;
    pageSize?: number;
    searchText?: string;
  }) => fetchJson<ListResponse<DataItem>>(`/data/list${buildQuery(params)}`),
  detail: (id: string) => fetchJson<DataDetail>(`/data/detail?id=${encodeURIComponent(id)}`),
  update: (payload: { dataId: string; q?: string; a?: string; indexes?: { text: string }[] }) =>
    fetchJson<IdResponse>("/data/update", { method: "PUT", body: JSON.stringify(payload) }),
  delete: (id: string) =>
    fetchJson<IdResponse>(`/data/delete?id=${encodeURIComponent(id)}`, { method: "DELETE" }),
};

export const searchApi = {
  search: (payload: SearchRequest) =>
    fetchJson<SearchHit[]>("/search", { method: "POST", body: JSON.stringify(payload) }),
};
