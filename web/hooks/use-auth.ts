"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import type { AuthUser } from "@/lib/types";

export const authKeys = {
  all: ["auth"] as const,
  me: ["auth", "me"] as const,
};

export function useMe() {
  return useQuery<AuthUser | null, Error>({
    queryKey: authKeys.me,
    queryFn: async () => {
      const res = await fetch("/api/proxy/auth/me");
      if (res.status === 401) return null;
      if (!res.ok) throw new Error("获取用户信息失败");
      return res.json();
    },
    retry: false,
    staleTime: 60 * 1000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: authKeys.me });
      toast.success("登录成功");
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.clear();
      toast.success("已退出登录");
    },
    onError: (error: Error) => {
      toast.error(`退出失败：${error.message}`);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: authApi.register,
    onSuccess: () => {
      toast.success("注册成功");
    },
    onError: (error: Error) => {
      toast.error(`注册失败：${error.message}`);
    },
  });
}
