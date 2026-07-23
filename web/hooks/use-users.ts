"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { userApi } from "@/lib/api";

export const userKeys = {
  all: ["users"] as const,
  list: (offset: number, pageSize: number) =>
    [...userKeys.all, "list", offset, pageSize] as const,
  search: (q: string) => [...userKeys.all, "search", q] as const,
};

export function useUsers(offset: number, pageSize: number) {
  return useQuery({
    queryKey: userKeys.list(offset, pageSize),
    queryFn: () => userApi.list({ offset, pageSize }),
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
      payload: {
        isActive?: boolean;
        isSuperuser?: boolean;
        allowApiKey?: boolean;
      };
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
