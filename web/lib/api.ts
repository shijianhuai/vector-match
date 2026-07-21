import type {
  AuthUser,
  Collection,
  DataDetail,
  DataItem,
  Dataset,
  DatasetMember,
  IdResponse,
  ListResponse,
  PushDataRequest,
  PushDataResponse,
  Role,
  SearchHit,
  SearchRequest,
  User,
} from "@/lib/types";

const baseUrl = "/api/proxy";

function fullUrl(path: string): string {
  if (path.startsWith("/api/")) return path;
  return `${baseUrl}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(fullUrl(path), {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    if (
      res.status === 401 &&
      path !== "/api/proxy/auth/me" &&
      typeof window !== "undefined"
    ) {
      await fetch("/api/auth/logout", { method: "POST" });
      window.location.href =
        "/login?from=" + encodeURIComponent(window.location.pathname);
      throw new Error("会话已过期，请重新登录");
    }

    const data = await res.json().catch(() => ({} as { detail?: unknown }));
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : data.detail
          ? JSON.stringify(data.detail)
          : null;
    throw new Error(detail || `请求失败：${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function buildQuery(
  params: Record<string, string | number | boolean | undefined>,
): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      sp.set(key, String(value));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export const authApi = {
  login: (payload: { username: string; password: string }) =>
    fetchJson<AuthUser>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () =>
    fetchJson<void>("/api/auth/logout", { method: "POST" }).catch(() => {}),
  register: (payload: {
    username: string;
    password: string;
    email?: string;
  }) =>
    fetchJson<IdResponse>("/api/proxy/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: () =>
    fetchJson<AuthUser | null>("/api/proxy/auth/me", { method: "GET" }).catch(
      () => null,
    ),
};

export const datasetApi = {
  create: (payload: { name: string; description?: string }) =>
    fetchJson<IdResponse>("/core/dataset/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  list: () => fetchJson<Dataset[]>("/core/dataset/list"),
  detail: (id: string) =>
    fetchJson<Dataset>(`/core/dataset/detail?id=${encodeURIComponent(id)}`),
  update: (payload: { id: string; name?: string; description?: string }) =>
    fetchJson<IdResponse>("/core/dataset/update", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    fetchJson<IdResponse>(
      `/core/dataset/delete?id=${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),
};

export const collectionApi = {
  create: (payload: {
    datasetId: string;
    parentId?: string;
    name: string;
    type: "folder" | "virtual";
  }) =>
    fetchJson<IdResponse>("/core/dataset/collection/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  list: (params: {
    datasetId: string;
    parentId?: string;
    offset?: number;
    pageSize?: number;
    searchText?: string;
  }) =>
    fetchJson<ListResponse<Collection>>(
      `/core/dataset/collection/list${buildQuery(params)}`,
    ),
  detail: (id: string) =>
    fetchJson<Collection>(
      `/core/dataset/collection/detail?id=${encodeURIComponent(id)}`,
    ),
  update: (payload: { id: string; name: string }) =>
    fetchJson<IdResponse>("/core/dataset/collection/update", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (collectionIds: string[]) =>
    fetchJson<IdResponse>("/core/dataset/collection/delete", {
      method: "DELETE",
      body: JSON.stringify({ collectionIds }),
    }),
};

export const dataApi = {
  push: (payload: PushDataRequest) =>
    fetchJson<PushDataResponse>("/core/dataset/data/pushData", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  list: (params: {
    collectionId: string;
    offset?: number;
    pageSize?: number;
    searchText?: string;
  }) =>
    fetchJson<ListResponse<DataItem>>(
      `/core/dataset/data/list${buildQuery(params)}`,
    ),
  detail: (id: string) =>
    fetchJson<DataDetail>(
      `/core/dataset/data/detail?id=${encodeURIComponent(id)}`,
    ),
  update: (payload: {
    dataId: string;
    q?: string;
    a?: string;
    indexes?: { text: string }[];
  }) =>
    fetchJson<IdResponse>("/core/dataset/data/update", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    fetchJson<IdResponse>(
      `/core/dataset/data/delete?id=${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),
};

export const searchApi = {
  search: (payload: SearchRequest) =>
    fetchJson<SearchHit[]>("/core/dataset/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const userApi = {
  list: (params: { offset: number; pageSize: number }) =>
    fetchJson<ListResponse<User>>(`/users/${buildQuery(params)}`),
  update: (
    userId: string,
    payload: { isActive?: boolean; isSuperuser?: boolean },
  ) =>
    fetchJson<void>(`/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

export const memberApi = {
  list: (datasetId: string) =>
    fetchJson<DatasetMember[]>(
      `/core/dataset/${encodeURIComponent(datasetId)}/members`,
    ),
  add: (
    datasetId: string,
    payload: { username: string; role: Role },
  ) =>
    fetchJson<IdResponse>(
      `/core/dataset/${encodeURIComponent(datasetId)}/members`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  updateRole: (
    datasetId: string,
    userId: string,
    payload: { role: Role },
  ) =>
    fetchJson<void>(
      `/core/dataset/${encodeURIComponent(datasetId)}/members/${encodeURIComponent(userId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    ),
  remove: (datasetId: string, userId: string) =>
    fetchJson<void>(
      `/core/dataset/${encodeURIComponent(datasetId)}/members/${encodeURIComponent(userId)}`,
      {
        method: "DELETE",
      },
    ),
};
