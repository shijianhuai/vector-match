"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRightIcon, Loader2Icon } from "lucide-react";
import { useRegister } from "@/hooks/use-auth";
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

const registerSchema = z
  .object({
    username: z.string().trim().min(1, "请输入用户名"),
    email: z
      .string()
      .trim()
      .max(100, "邮箱过长")
      .optional()
      .refine(
        (value) => !value || value === "" || /^\S+@\S+\.\S+$/.test(value),
        { message: "邮箱格式不正确" },
      ),
    password: z.string().min(6, "密码至少 6 位"),
    confirmPassword: z.string().min(1, "请确认密码"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "两次输入的密码不一致",
    path: ["confirmPassword"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

function RegisterForm() {
  const router = useRouter();
  const register = useRegister();

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const payload = {
      username: values.username,
      password: values.password,
      email: values.email || undefined,
    };
    try {
      await register.mutateAsync(payload);
      router.push(`/login?username=${encodeURIComponent(values.username)}`);
    } catch {
      // 错误已由 hook toast 处理，保持表单状态
    }
  });

  return (
    <AuthShell
      eyebrow="VECTOR MATCH · CONSOLE"
      title="创建账号"
      description="注册后即可建立知识库，推送短文本并开始检索。"
      footer={
        <>
          已有账号？{" "}
          <Link href="/login" className={authLinkClass}>
            登录
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-5">
        {register.isError && (
          <p className={authErrorClass}>{register.error.message}</p>
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
          <Label htmlFor="email" className={authLabelClass}>
            邮箱（可选）
          </Label>
          <Input
            id="email"
            type="email"
            placeholder="name@example.com"
            autoComplete="email"
            aria-invalid={Boolean(form.formState.errors.email)}
            className={authFieldClass}
            {...form.register("email")}
          />
          {form.formState.errors.email && (
            <p className={authFieldErrorClass}>
              {form.formState.errors.email.message}
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
            placeholder="至少 6 位"
            autoComplete="new-password"
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
        <div className="grid gap-2">
          <Label htmlFor="confirmPassword" className={authLabelClass}>
            确认密码
          </Label>
          <Input
            id="confirmPassword"
            type="password"
            placeholder="再次输入密码"
            autoComplete="new-password"
            aria-invalid={Boolean(form.formState.errors.confirmPassword)}
            className={authFieldClass}
            {...form.register("confirmPassword")}
          />
          {form.formState.errors.confirmPassword && (
            <p className={authFieldErrorClass}>
              {form.formState.errors.confirmPassword.message}
            </p>
          )}
        </div>
        <Button
          type="submit"
          disabled={register.isPending}
          className={authSubmitClass}
        >
          {register.isPending ? (
            <Loader2Icon className="animate-spin" />
          ) : (
            <ArrowRightIcon className="order-last transition-transform duration-200 group-hover/button:translate-x-0.5" />
          )}
          创建账号
        </Button>
      </form>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <React.Suspense
      fallback={
        <AuthShell
          eyebrow="VECTOR MATCH · CONSOLE"
          title="创建账号"
          description="注册后即可建立知识库，推送短文本并开始检索。"
          footer={null}
        >
          <div className="grid gap-5" aria-hidden>
            {[64, 96, 48, 80].map((labelWidth, i) => (
              <div key={i} className="grid gap-2">
                <Skeleton
                  className="h-3.5 bg-[#EEEAE2]"
                  style={{ width: labelWidth }}
                />
                <Skeleton className="h-11 w-full bg-[#F4F1EA]" />
              </div>
            ))}
            <Skeleton className="mt-1 h-11 w-full bg-[#E7E3D9]" />
          </div>
        </AuthShell>
      }
    >
      <RegisterForm />
    </React.Suspense>
  );
}
