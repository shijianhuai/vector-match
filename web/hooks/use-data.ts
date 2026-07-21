"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { dataApi } from "@/lib/api";
import type { DataItem, ListResponse } from "@/lib/types";

export const dataKeys = {
  all: (collectionId: string) => ["data", collectionId] as const,
  list: (
    collectionId: string,
    offset: number,
    pageSize: number,
    searchText?: string
  ) =>
    ["data", collectionId, "list", offset, pageSize, searchText] as const,
  detail: (id: string) => ["data", "detail", id] as const,
};

export function useDataList(params: {
  collectionId: string;
  offset: number;
  pageSize: number;
  searchText?: string;
}) {
  return useQuery({
    queryKey: dataKeys.list(
      params.collectionId,
      params.offset,
      params.pageSize,
      params.searchText
    ),
    queryFn: () =>
      dataApi.list({ ...params, searchText: params.searchText || undefined }),
    refetchInterval: (query) => {
      const data = query.state.data as ListResponse<DataItem> | undefined;
      return data?.list.some((item) => !item.trained) ? 4000 : false;
    },
  });
}

export function useDataDetail(id: string) {
  return useQuery({
    queryKey: dataKeys.detail(id),
    queryFn: () => dataApi.detail(id),
    enabled: Boolean(id),
  });
}

export function usePushData(collectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dataApi.push,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dataKeys.all(collectionId) });
      toast.success("数据新增成功");
    },
    onError: (error: Error) => {
      toast.error(`新增失败：${error.message}`);
    },
  });
}

export function useUpdateData(collectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dataApi.update,
    onSuccess: ({ id: dataId }) => {
      queryClient.invalidateQueries({ queryKey: dataKeys.detail(dataId) });
      queryClient.invalidateQueries({ queryKey: dataKeys.all(collectionId) });
      toast.success("保存成功");
    },
    onError: (error: Error) => {
      toast.error(`保存失败：${error.message}`);
    },
  });
}

export function useDeleteData(collectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dataApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dataKeys.all(collectionId) });
      toast.success("数据已删除");
    },
    onError: (error: Error) => {
      toast.error(`删除失败：${error.message}`);
    },
  });
}
