"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { collectionApi } from "@/lib/api";
import type { Collection } from "@/lib/types";

export const collectionKeys = {
  all: ["collections"] as const,
  lists: () => [...collectionKeys.all, "list"] as const,
  list: (params: {
    datasetId: string;
    parentId: string | null;
    offset: number;
    pageSize: number;
    searchText: string;
  }) => [...collectionKeys.lists(), params] as const,
  detail: (id: string) => [...collectionKeys.all, "detail", id] as const,
  ancestors: (parentId: string) =>
    [...collectionKeys.all, "ancestors", parentId] as const,
};

export function useCollections(params: {
  datasetId: string;
  parentId: string | null;
  offset: number;
  pageSize: number;
  searchText: string;
}) {
  return useQuery({
    queryKey: collectionKeys.list(params),
    queryFn: () =>
      collectionApi.list({
        datasetId: params.datasetId,
        parentId: params.parentId ?? undefined,
        offset: params.offset,
        pageSize: params.pageSize,
        searchText: params.searchText || undefined,
      }),
  });
}

export interface CollectionAncestor {
  id: string;
  name: string;
}

export function useCollectionAncestors(parentId: string | null) {
  return useQuery({
    queryKey: parentId
      ? collectionKeys.ancestors(parentId)
      : collectionKeys.all,
    queryFn: async (): Promise<CollectionAncestor[]> => {
      if (!parentId) return [];
      const chain: CollectionAncestor[] = [];
      let currentId: string | null = parentId;
      for (let i = 0; i < 10; i++) {
        try {
          const detail: Collection = await collectionApi.detail(currentId);
          chain.unshift({ id: detail.id, name: detail.name });
          if (!detail.parentId) break;
          currentId = detail.parentId;
        } catch {
          break;
        }
      }
      return chain;
    },
    enabled: Boolean(parentId),
  });
}

export function useCreateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: collectionApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.lists() });
      toast.success("集合创建成功");
    },
    onError: (error: Error) => {
      toast.error(`创建失败：${error.message}`);
    },
  });
}

export function useUpdateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: collectionApi.update,
    onSuccess: ({ id }) => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.lists() });
      queryClient.invalidateQueries({ queryKey: collectionKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: collectionKeys.all });
      toast.success("保存成功");
    },
    onError: (error: Error) => {
      toast.error(`保存失败：${error.message}`);
    },
  });
}

export function useDeleteCollections() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: collectionApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.all });
      toast.success("删除成功");
    },
    onError: (error: Error) => {
      toast.error(`删除失败：${error.message}`);
    },
  });
}
