"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/hooks/use-auth";
import { useUpdateUser, useUsers } from "@/hooks/use-users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { User } from "@/lib/types";

const PAGE_SIZE = 20;

function formatCreateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function UserRow({ user, currentUserId }: { user: User; currentUserId: number }) {
  const update = useUpdateUser();
  const isSelf = user.id === currentUserId;
  const [pending, setPending] = React.useState<{
    type: "active" | "superuser";
    value: boolean;
  } | null>(null);

  const handleActiveChange = (checked: boolean) => {
    if (!checked) {
      setPending({ type: "active", value: checked });
    } else {
      update.mutate({ userId: user.id, payload: { isActive: checked } });
    }
  };

  const handleSuperuserChange = (checked: boolean) => {
    if (checked) {
      setPending({ type: "superuser", value: checked });
    } else {
      update.mutate({ userId: user.id, payload: { isSuperuser: checked } });
    }
  };

  const handleConfirm = () => {
    if (!pending) return;
    const payload =
      pending.type === "active"
        ? { isActive: pending.value }
        : { isSuperuser: pending.value };
    update.mutate({ userId: user.id, payload });
    setPending(null);
  };

  const handleCancel = () => setPending(null);

  const pendingLabel =
    pending?.type === "active" ? "禁用用户" : "设为超管";
  const pendingDescription =
    pending?.type === "active"
      ? `确定禁用用户「${user.username}」吗？该用户将被登出且无法登录。`
      : `确定将用户「${user.username}」设为站点超管吗？该用户将获得全部管理权限。`;

  return (
    <>
      <TableRow>
        <TableCell className="font-medium">
          <span className="inline-flex items-center gap-2">
            {user.username}
            {isSelf && <Badge variant="outline">我</Badge>}
          </span>
        </TableCell>
        <TableCell className="max-w-56 truncate">
          {user.email ?? "—"}
        </TableCell>
        <TableCell className="w-44 text-muted-foreground tabular-nums">
          {formatCreateTime(user.createTime)}
        </TableCell>
        <TableCell>
          <Switch
            checked={user.isActive}
            disabled={isSelf || update.isPending}
            onCheckedChange={handleActiveChange}
            aria-label={`${user.username} 是否启用`}
          />
        </TableCell>
        <TableCell>
          <Switch
            checked={user.isSuperuser}
            disabled={isSelf || update.isPending}
            onCheckedChange={handleSuperuserChange}
            aria-label={`${user.username} 是否超管`}
          />
        </TableCell>
      </TableRow>
      <AlertDialog open={pending !== null} onOpenChange={handleCancel}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认{pendingLabel}</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDescription}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={update.isPending}>
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={update.isPending}
              onClick={handleConfirm}
            >
              确认
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default function UsersSettingsPage() {
  const router = useRouter();
  const { data: me, isLoading: isLoadingMe } = useMe();
  const [offset, setOffset] = React.useState(0);
  const { data, isLoading, isError, refetch } = useUsers(offset, PAGE_SIZE);

  if (isLoadingMe) {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
        <Skeleton className="h-8 w-40" />
        <div className="mt-6 space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      </div>
    );
  }

  if (!me?.isSuperuser) {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 py-24 text-center">
        <p className="text-sm font-medium">无权限访问此页面</p>
        <p className="mt-1 text-sm text-muted-foreground">
          只有站点管理员才能管理用户。
        </p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push("/datasets")}
        >
          返回知识库
        </Button>
      </div>
    );
  }

  const total = data?.total ?? 0;
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">用户管理</h1>

      {isLoading ? (
        <div className="mt-6 space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : isError ? (
        <div className="mt-6 rounded-lg border bg-card py-12 text-center">
          <p className="text-sm text-destructive">加载失败，请稍后重试</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => refetch()}
          >
            重试
          </Button>
        </div>
      ) : (
        <>
          <div className="mt-6 rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用户名</TableHead>
                  <TableHead>邮箱</TableHead>
                  <TableHead className="w-44">创建时间</TableHead>
                  <TableHead className="w-20">启用</TableHead>
                  <TableHead className="w-20">超管</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.list.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="py-12 text-center text-sm text-muted-foreground"
                    >
                      暂无用户
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.list.map((user) => (
                    <UserRow key={user.id} user={user} currentUserId={me.id} />
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <div className="text-muted-foreground tabular-nums">
              共 {total} 条
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                disabled={!hasPrev}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                disabled={!hasNext}
              >
                下一页
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
