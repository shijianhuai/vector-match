"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { datasetApi } from "@/lib/api";

export const datasetKeys = {
  all: ["datasets"] as const,
  detail: (id: string) => ["datasets", id] as const,
};

export function useDatasets() {
  return useQuery({
    queryKey: datasetKeys.all,
    queryFn: datasetApi.list,
  });
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: datasetKeys.detail(id),
    queryFn: () => datasetApi.detail(id),
    enabled: Boolean(id),
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: datasetApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: datasetKeys.all });
      toast.success("知识库创建成功");
    },
    onError: (error: Error) => {
      toast.error(`创建失败：${error.message}`);
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: datasetApi.update,
    onSuccess: ({ id }) => {
      queryClient.invalidateQueries({ queryKey: datasetKeys.all });
      queryClient.invalidateQueries({ queryKey: datasetKeys.detail(id) });
      toast.success("保存成功");
    },
    onError: (error: Error) => {
      toast.error(`保存失败：${error.message}`);
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: datasetApi.delete,
    onSuccess: ({ id }) => {
      queryClient.removeQueries({ queryKey: datasetKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: datasetKeys.all });
      toast.success("知识库已删除");
    },
    onError: (error: Error) => {
      toast.error(`删除失败：${error.message}`);
    },
  });
}
