"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiKeyApi } from "@/lib/api";

export const apiKeyKeys = {
  all: ["apiKeys"] as const,
  list: (offset: number, pageSize: number) =>
    [...apiKeyKeys.all, "list", offset, pageSize] as const,
};

export function useApiKeys(offset: number, pageSize: number) {
  return useQuery({
    queryKey: apiKeyKeys.list(offset, pageSize),
    queryFn: () => apiKeyApi.list({ offset, pageSize }),
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string }) => apiKeyApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.all });
      toast.success("API Key 创建成功");
    },
    onError: (error: Error) => {
      toast.error(`创建失败：${error.message}`);
    },
  });
}

export function useUpdateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: { name: string };
    }) => apiKeyApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.all });
      toast.success("API Key 更新成功");
    },
    onError: (error: Error) => {
      toast.error(`更新失败：${error.message}`);
    },
  });
}

export function useDeleteApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiKeyApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.all });
      toast.success("API Key 删除成功");
    },
    onError: (error: Error) => {
      toast.error(`删除失败：${error.message}`);
    },
  });
}
