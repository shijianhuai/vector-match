"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { CheckIcon, CopyIcon, Loader2Icon } from "lucide-react";
import {
  useDataset,
  useDeleteDataset,
  useUpdateDataset,
} from "@/hooks/use-datasets";
import { MemberPanel } from "@/components/members/member-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
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

const settingsFormSchema = z.object({
  name: z.string().trim().min(1, "请输入名称").max(50, "名称不能超过 50 字"),
  description: z
    .string()
    .trim()
    .max(200, "描述不能超过 200 字")
    .optional(),
});

type SettingsFormValues = z.infer<typeof settingsFormSchema>;

export default function DatasetSettingsPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const router = useRouter();

  const { data: dataset, isLoading } = useDataset(datasetId);
  const updateMutation = useUpdateDataset();
  const deleteMutation = useDeleteDataset();

  const myRole = dataset?.myRole ?? "viewer";
  const canEdit = myRole === "owner" || myRole === "editor";
  const canDelete = myRole === "owner";

  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsFormSchema),
    values: {
      name: dataset?.name ?? "",
      description: dataset?.description ?? "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await updateMutation.mutateAsync({
        id: datasetId,
        name: values.name,
        description: values.description ?? "",
      });
    } catch {
      // 错误已由 hook toast 处理
    }
  });

  const handleCopyId = async () => {
    if (!dataset) return;
    try {
      await navigator.clipboard.writeText(dataset.id);
      setCopied(true);
      toast.success("已复制数据集 ID");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(datasetId);
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    setDeleteOpen(false);
    router.push("/datasets");
  };

  if (isLoading) {
    return (
      <div className="max-w-lg space-y-6">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-lg space-y-8">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-2">
          <Label htmlFor="settings-name">
            名称 <span className="text-destructive">*</span>
          </Label>
          <Input
            id="settings-name"
            disabled={!canEdit}
            aria-invalid={Boolean(form.formState.errors.name)}
            {...form.register("name")}
          />
          {form.formState.errors.name && (
            <p className="text-xs text-destructive">
              {form.formState.errors.name.message}
            </p>
          )}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="settings-description">描述</Label>
          <Textarea
            id="settings-description"
            rows={3}
            disabled={!canEdit}
            placeholder="可选，简要说明知识库用途"
            aria-invalid={Boolean(form.formState.errors.description)}
            {...form.register("description")}
          />
          {form.formState.errors.description && (
            <p className="text-xs text-destructive">
              {form.formState.errors.description.message}
            </p>
          )}
        </div>
        {canEdit && (
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            保存
          </Button>
        )}
      </form>

      <div className="space-y-3 border-t pt-6">
        <h2 className="text-sm font-medium">基本信息</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <dt className="w-20 shrink-0 text-muted-foreground">数据集 ID</dt>
            <dd className="flex min-w-0 items-center gap-1.5">
              <code className="truncate rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                {dataset?.id}
              </code>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label="复制数据集 ID"
                onClick={handleCopyId}
              >
                {copied ? <CheckIcon /> : <CopyIcon />}
              </Button>
            </dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="w-20 shrink-0 text-muted-foreground">向量模型</dt>
            <dd>{dataset?.vectorModel ?? "—"}</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="w-20 shrink-0 text-muted-foreground">我的角色</dt>
            <dd>{myRole}</dd>
          </div>
        </dl>
      </div>

      <MemberPanel datasetId={datasetId} myRole={myRole} />

      {canDelete && (
        <Card className="gap-3 border-destructive/50 p-4">
          <h2 className="text-sm font-medium text-destructive">危险区</h2>
          <p className="text-sm text-muted-foreground">
            删除知识库将级联删除其下全部集合与数据，该操作无法恢复。
          </p>
          <div>
            <Button
              variant="destructive"
              onClick={() => setDeleteOpen(true)}
            >
              删除知识库
            </Button>
          </div>
        </Card>
      )}

      <AlertDialog
        open={deleteOpen}
        onOpenChange={(open) => {
          if (!open && !deleteMutation.isPending) setDeleteOpen(false);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除知识库</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除「{dataset?.name}」吗？该操作将级联删除其下全部集合与数据，且无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={handleDelete}
            >
              {deleteMutation.isPending && (
                <Loader2Icon className="animate-spin" />
              )}
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
