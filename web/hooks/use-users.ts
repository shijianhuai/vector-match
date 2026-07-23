"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { userApi } from "@/lib/api";
import type { UserUpdatePayload } from "@/lib/api";
import type { SiteRole } from "@/lib/types";

export const userKeys = {
  all: ["users"] as const,
  list: (offset: number, pageSize: number, isApproved?: boolean) =>
    [...userKeys.all, "list", offset, pageSize, isApproved ?? "all"] as const,
  search: (q: string) => [...userKeys.all, "search", q] as const,
};

export function useUsers(offset: number, pageSize: number, isApproved?: boolean) {
  return useQuery({
    queryKey: userKeys.list(offset, pageSize, isApproved),
    queryFn: () => userApi.list({ offset, pageSize, isApproved }),
  });
}

export function useUserSearch(q: string) {
  const keyword = q.trim();
  return useQuery({
    queryKey: userKeys.search(keyword),
    queryFn: () => userApi.search(keyword),
    enabled: keyword.length > 0,
    staleTime: 30 * 1000,
    placeholderData: (previous) => previous,
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      payload,
    }: {
      userId: number;
      payload: UserUpdatePayload;
    }) => userApi.update(userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all });
      toast.success("用户更新成功");
    },
    onError: (error: Error) => {
      toast.error(`更新失败：${error.message}`);
    },
  });
}

export function roleLabel(role: SiteRole): string {
  switch (role) {
    case "superadmin":
      return "超级管理员";
    case "admin":
      return "管理员";
    case "user":
      return "普通用户";
    default:
      return role;
  }
}
