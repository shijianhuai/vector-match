"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  CheckIcon,
  CopyIcon,
  EyeIcon,
  EyeOffIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
} from "lucide-react";
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  useUpdateApiKey,
} from "@/hooks/use-api-keys";
import { useMe } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { toast } from "sonner";
import type { ApiKey } from "@/lib/types";

const PAGE_SIZE = 20;

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function maskKey(key: string): string {
  if (key.length <= 12) return key;
  const prefix = key.slice(0, 7); // sk- + 4 chars
  const suffix = key.slice(-4);
  return `${prefix}${"*".repeat(23)}${suffix}`;
}

function useClipboard() {
  const [copied, setCopied] = React.useState(false);
  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const copy = React.useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 2000);
      toast.success("已复制");
    } catch {
      toast.error("复制失败");
    }
  }, []);

  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return { copied, copy };
}

function CopyButton({ value }: { value: string }) {
  const { copied, copy } = useClipboard();
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={copied ? "已复制" : "复制"}
      onClick={() => copy(value)}
      className="size-7"
    >
      {copied ? (
        <CheckIcon className="size-4 text-green-600" />
      ) : (
        <CopyIcon className="size-4" />
      )}
    </Button>
  );
}

function KeyCell({ apiKey }: { apiKey: ApiKey }) {
  const [visible, setVisible] = React.useState(false);
  return (
    <span className="inline-flex items-center gap-2">
      <code className="font-mono text-sm">
        {visible ? apiKey.key : maskKey(apiKey.key)}
      </code>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={visible ? "隐藏" : "显示"}
        onClick={() => setVisible((v) => !v)}
        className="size-7"
      >
        {visible ? (
          <EyeOffIcon className="size-4" />
        ) : (
          <EyeIcon className="size-4" />
        )}
      </Button>
      <CopyButton value={apiKey.key} />
    </span>
  );
}

function CreateApiKeyDialog({
  onCreated,
}: {
  onCreated: (apiKey: ApiKey) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [error, setError] = React.useState("");
  const create = useCreateApiKey();

  const trimmed = name.trim();
  const canSubmit = trimmed.length > 0;

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) {
      setName("");
      setError("");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) {
      setError("名称不能为空");
      return;
    }
    setError("");
    create.mutate(
      { name: trimmed },
      {
        onSuccess: (data) => {
          setOpen(false);
          setName("");
          onCreated(data);
        },
      },
    );
  };

  return (
    <>
      <Button variant="default" size="sm" onClick={() => setOpen(true)}>
        <PlusIcon className="size-4" />
        新建 API Key
      </Button>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-sm">
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>新建 API Key</DialogTitle>
              <DialogDescription>
                创建后请立即复制保存，完整 key 仅展示一次。
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-2 py-4">
              <Label htmlFor="api-key-name">名称</Label>
              <Input
                id="api-key-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (error) setError("");
                }}
                placeholder="例如：生产环境脚本"
                aria-invalid={!!error}
              />
              {error && (
                <p className="text-xs text-destructive">{error}</p>
              )}
            </div>
            <DialogFooter>
              <Button
                type="submit"
                disabled={!canSubmit || create.isPending}
              >
                {create.isPending ? "创建中..." : "创建"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CreatedApiKeyDialog({
  apiKey,
  open,
  onOpenChange,
}: {
  apiKey: ApiKey | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { copied, copy } = useClipboard();
  if (!apiKey) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>保存 API Key</DialogTitle>
          <DialogDescription>
            请立即复制保存，关闭后将无法再次查看完整 key。
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="flex items-center gap-2 rounded-lg border bg-muted p-3">
            <code className="flex-1 break-all font-mono text-sm">{apiKey.key}</code>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copy(apiKey.key)}
              className="shrink-0"
            >
              {copied ? (
                <>
                  <CheckIcon className="size-4 text-green-600" />
                  已复制
                </>
              ) : (
                <>
                  <CopyIcon className="size-4" />
                  复制
                </>
              )}
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>我已保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditApiKeyDialog({
  apiKey,
  open,
  onOpenChange,
}: {
  apiKey: ApiKey | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [name, setName] = React.useState(apiKey?.name ?? "");
  const [error, setError] = React.useState("");
  const update = useUpdateApiKey();

  const trimmed = name.trim();
  const canSubmit = trimmed.length > 0;

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next);
    if (!next) {
      setError("");
      setName(apiKey?.name ?? "");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey) return;
    if (!canSubmit) {
      setError("名称不能为空");
      return;
    }
    setError("");
    update.mutate(
      { id: apiKey.id, payload: { name: trimmed } },
      {
        onSuccess: () => onOpenChange(false),
      },
    );
  };

  if (!apiKey) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>编辑 API Key</DialogTitle>
          </DialogHeader>
          <div className="grid gap-2 py-4">
            <Label htmlFor="edit-api-key-name">名称</Label>
            <Input
              id="edit-api-key-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError("");
              }}
              aria-invalid={!!error}
            />
            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={!canSubmit || update.isPending}
            >
              {update.isPending ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteApiKeyDialog({
  apiKey,
  open,
  onOpenChange,
}: {
  apiKey: ApiKey | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const remove = useDeleteApiKey();
  if (!apiKey) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>确认删除 API Key</AlertDialogTitle>
          <AlertDialogDescription>
            确定删除「{apiKey.name}」吗？删除后，使用该 key 的外部系统将无法访问。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={remove.isPending}>取消</AlertDialogCancel>
          <AlertDialogAction
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(apiKey.id, { onSuccess: () => onOpenChange(false) })
            }
            variant="destructive"
          >
            删除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default function ApiKeysSettingsPage() {
  const router = useRouter();
  const { data: me, isLoading: isLoadingMe } = useMe();
  const [offset, setOffset] = React.useState(0);
  const { data, isLoading, isError, refetch } = useApiKeys(offset, PAGE_SIZE);
  const [createdApiKey, setCreatedApiKey] = React.useState<ApiKey | null>(
    null,
  );
  const [editingApiKey, setEditingApiKey] = React.useState<ApiKey | null>(
    null,
  );
  const [deletingApiKey, setDeletingApiKey] = React.useState<ApiKey | null>(
    null,
  );

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

  if (!me || (me.role !== "admin" && me.role !== "superadmin")) {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 py-24 text-center">
        <p className="text-sm font-medium">无权限访问此页面</p>
        <p className="mt-1 text-sm text-muted-foreground">
          只有管理员和超级管理员可以使用 API Key 管理。
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
        API Keys
      </p>
      <div className="mt-2 flex items-center justify-between">
        <h1 className="font-display text-[28px] font-semibold tracking-[-0.02em]">
          API Key 管理
        </h1>
        <CreateApiKeyDialog onCreated={setCreatedApiKey} />
      </div>

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
                  <TableHead>名称</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead className="w-44">创建时间</TableHead>
                  <TableHead className="w-44">最新使用时间</TableHead>
                  <TableHead className="w-24">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.list.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="py-12 text-center text-sm text-muted-foreground"
                    >
                      暂无 API Key
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.list.map((apiKey) => (
                    <TableRow key={apiKey.id}>
                      <TableCell className="font-medium">{apiKey.name}</TableCell>
                      <TableCell>
                        <KeyCell apiKey={apiKey} />
                      </TableCell>
                      <TableCell className="w-44 text-muted-foreground tabular-nums">
                        {formatTime(apiKey.createTime)}
                      </TableCell>
                      <TableCell className="w-44 text-muted-foreground tabular-nums">
                        {formatTime(apiKey.lastUsedAt)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="编辑"
                            onClick={() => setEditingApiKey(apiKey)}
                          >
                            <PencilIcon className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="删除"
                            onClick={() => setDeletingApiKey(apiKey)}
                          >
                            <TrashIcon className="size-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <div className="text-muted-foreground tabular-nums">共 {total} 条</div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setOffset((prev) => Math.max(0, prev - PAGE_SIZE))
                }
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

      <CreatedApiKeyDialog
        apiKey={createdApiKey}
        open={createdApiKey !== null}
        onOpenChange={(open) => {
          if (!open) setCreatedApiKey(null);
        }}
      />
      <EditApiKeyDialog
        key={editingApiKey?.id}
        apiKey={editingApiKey}
        open={editingApiKey !== null}
        onOpenChange={(open) => {
          if (!open) setEditingApiKey(null);
        }}
      />
      <DeleteApiKeyDialog
        apiKey={deletingApiKey}
        open={deletingApiKey !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingApiKey(null);
        }}
      />
    </div>
  );
}
