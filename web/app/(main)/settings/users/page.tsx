"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckIcon, Loader2Icon, ShieldCheckIcon } from "lucide-react";
import { useMe } from "@/hooks/use-auth";
import { roleLabel, useUpdateUser, useUsers } from "@/hooks/use-users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tabs,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SiteRole, User } from "@/lib/types";

const PAGE_SIZE = 20;
const ROLE_OPTIONS: { value: SiteRole; label: string }[] = [
  { value: "superadmin", label: "超级管理员" },
  { value: "admin", label: "管理员" },
  { value: "user", label: "普通用户" },
];

type Filter = "all" | "pending" | "approved";

function formatCreateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function UserStatusBadge({ user }: { user: User }) {
  if (!user.isApproved) {
    return <Badge variant="outline">待审核</Badge>;
  }
  return <Badge variant="secondary">已启用</Badge>;
}

function UserRoleBadge({ role }: { role: SiteRole }) {
  const variant =
    role === "superadmin"
      ? "default"
      : role === "admin"
        ? "secondary"
        : "outline";
  return (
    <Badge variant={variant} className="capitalize">
      {roleLabel(role)}
    </Badge>
  );
}

function UserRow({ user, currentUserId }: { user: User; currentUserId: number }) {
  const update = useUpdateUser();
  const isSelf = user.id === currentUserId;

  const handleRoleChange = (role: SiteRole) => {
    update.mutate({ userId: user.id, payload: { role } });
  };

  const handleApprove = () => {
    update.mutate({ userId: user.id, payload: { isApproved: true } });
  };

  const handleActiveChange = (checked: boolean) => {
    update.mutate({ userId: user.id, payload: { isActive: checked } });
  };

  return (
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
        <UserStatusBadge user={user} />
      </TableCell>
      <TableCell>
        <Select
          value={user.role}
          onValueChange={(value) => handleRoleChange(value as SiteRole)}
          disabled={isSelf || update.isPending}
        >
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLE_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        <Switch
          checked={user.isActive}
          disabled={isSelf || update.isPending}
          onCheckedChange={handleActiveChange}
          aria-label={`${user.username} 是否启用`}
        />
      </TableCell>
      <TableCell className="w-32">
        {!user.isApproved && !isSelf ? (
          <Button
            size="sm"
            variant="default"
            disabled={update.isPending}
            onClick={handleApprove}
          >
            {update.isPending ? (
              <Loader2Icon className="animate-spin" />
            ) : (
              <CheckIcon />
            )}
            通过审核
          </Button>
        ) : (
          <UserRoleBadge role={user.role} />
        )}
      </TableCell>
    </TableRow>
  );
}

export default function UsersSettingsPage() {
  const router = useRouter();
  const { data: me, isLoading: isLoadingMe } = useMe();
  const [filter, setFilter] = React.useState<Filter>("all");
  const [offset, setOffset] = React.useState(0);
  const isApproved =
    filter === "pending" ? false : filter === "approved" ? true : undefined;
  const { data, isLoading, isError, refetch } = useUsers(offset, PAGE_SIZE, isApproved);

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

  if (!me || me.role !== "superadmin") {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 py-24 text-center">
        <ShieldCheckIcon className="mx-auto size-10 text-muted-foreground" />
        <p className="mt-4 text-sm font-medium">无权限访问此页面</p>
        <p className="mt-1 text-sm text-muted-foreground">
          只有超级管理员才能管理用户。
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
      <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-muted-foreground">
        Users
      </p>
      <h1 className="mt-2 font-display text-[28px] font-semibold tracking-[-0.02em]">
        用户管理
      </h1>

      <Tabs
        value={filter}
        onValueChange={(value) => {
          setFilter(value as Filter);
          setOffset(0);
        }}
        className="mt-6"
      >
        <TabsList>
          <TabsTrigger value="all">全部</TabsTrigger>
          <TabsTrigger value="pending">待审核</TabsTrigger>
          <TabsTrigger value="approved">已审核</TabsTrigger>
        </TabsList>
      </Tabs>

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
                  <TableHead className="w-24">状态</TableHead>
                  <TableHead className="w-36">站点角色</TableHead>
                  <TableHead className="w-20">启用</TableHead>
                  <TableHead className="w-32">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.list.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
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
