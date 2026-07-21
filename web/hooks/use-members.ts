"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { memberApi } from "@/lib/api";
import type { DatasetMember, Role } from "@/lib/types";

export const memberKeys = {
  all: (datasetId: string) => ["members", datasetId] as const,
  list: (datasetId: string) => [...memberKeys.all(datasetId), "list"] as const,
};

export function useMembers(datasetId: string) {
  return useQuery<DatasetMember[], Error>({
    queryKey: memberKeys.list(datasetId),
    queryFn: () => memberApi.list(datasetId),
    enabled: Boolean(datasetId),
  });
}

export function useAddMember(datasetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { username: string; role: Role }) =>
      memberApi.add(datasetId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memberKeys.all(datasetId) });
      toast.success("成员添加成功");
    },
    onError: (error: Error) => {
      toast.error(`添加失败：${error.message}`);
    },
  });
}

export function useUpdateMemberRole(datasetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      memberApi.updateRole(datasetId, userId, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memberKeys.all(datasetId) });
      toast.success("角色已更新");
    },
    onError: (error: Error) => {
      toast.error(`更新失败：${error.message}`);
    },
  });
}

export function useRemoveMember(datasetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => memberApi.remove(datasetId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memberKeys.all(datasetId) });
      toast.success("成员已移除");
    },
    onError: (error: Error) => {
      toast.error(`移除失败：${error.message}`);
    },
  });
}
