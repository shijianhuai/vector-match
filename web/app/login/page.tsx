"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRightIcon, Loader2Icon } from "lucide-react";
import { useLogin } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AuthShell,
  authErrorClass,
  authFieldClass,
  authFieldErrorClass,
  authLabelClass,
  authLinkClass,
  authSubmitClass,
} from "@/components/auth/auth-shell";

const loginSchema = z.object({
  username: z.string().trim().min(1, "请输入用户名"),
  password: z.string().min(1, "请输入密码"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

function LoginForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const login = useLogin();

  const from = searchParams.get("from");
  const defaultUsername = searchParams.get("username") ?? "";

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: defaultUsername, password: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      const redirectTo =
        from && from.startsWith("/") ? from : "/datasets";
      router.push(redirectTo);
    } catch {
      // 错误已在表单内联显示，保持表单状态
    }
  });

  return (
    <AuthShell
      eyebrow="VECTOR MATCH · CONSOLE"
      title="登录"
      description="登录以管理你的知识库与语义检索。"
      footer={
        <>
          没有账号？{" "}
          <Link href="/register" className={authLinkClass}>
            创建账号
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-5">
        {login.isError && (
          <p className={authErrorClass}>{login.error.message}</p>
        )}
        <div className="grid gap-2">
          <Label htmlFor="username" className={authLabelClass}>
            用户名
          </Label>
          <Input
            id="username"
            placeholder="输入用户名"
            autoComplete="username"
            autoFocus
            aria-invalid={Boolean(form.formState.errors.username)}
            className={authFieldClass}
            {...form.register("username")}
          />
          {form.formState.errors.username && (
            <p className={authFieldErrorClass}>
              {form.formState.errors.username.message}
            </p>
          )}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password" className={authLabelClass}>
            密码
          </Label>
          <Input
            id="password"
            type="password"
            placeholder="输入密码"
            autoComplete="current-password"
            aria-invalid={Boolean(form.formState.errors.password)}
            className={authFieldClass}
            {...form.register("password")}
          />
          {form.formState.errors.password && (
            <p className={authFieldErrorClass}>
              {form.formState.errors.password.message}
            </p>
          )}
        </div>
        <Button type="submit" disabled={login.isPending} className={authSubmitClass}>
          {login.isPending ? (
            <Loader2Icon className="animate-spin" />
          ) : (
            <ArrowRightIcon className="order-last transition-transform duration-200 group-hover/button:translate-x-0.5" />
          )}
          进入控制台
        </Button>
      </form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense
      fallback={
        <AuthShell
          eyebrow="VECTOR MATCH · CONSOLE"
          title="登录"
          description="登录以管理你的知识库与语义检索。"
          footer={null}
        >
          <div className="grid gap-5" aria-hidden>
            <Skeleton className="h-11 w-full bg-white/[0.06]" />
            <Skeleton className="h-11 w-full bg-white/[0.06]" />
            <Skeleton className="h-11 w-full bg-white/[0.06]" />
          </div>
        </AuthShell>
      }
    >
      <LoginForm />
    </React.Suspense>
  );
}
