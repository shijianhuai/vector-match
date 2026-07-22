"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  DatabaseIcon,
  EllipsisIcon,
  Loader2Icon,
  PlusIcon,
  SearchIcon,
} from "lucide-react";
import type { Dataset } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useCreateDataset,
  useDatasets,
  useDeleteDataset,
  useUpdateDataset,
} from "@/hooks/use-datasets";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const datasetFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "请输入名称")
    .max(50, "名称不能超过 50 字"),
  description: z
    .string()
    .trim()
    .max(200, "描述不能超过 200 字")
    .optional(),
});

type DatasetFormValues = z.infer<typeof datasetFormSchema>;

type FormDialogState =
  | { mode: "create" }
  | { mode: "edit"; dataset: Dataset }
  | null;

function DatasetFormDialog({
  state,
  onClose,
}: {
  state: FormDialogState;
  onClose: () => void;
}) {
  const createMutation = useCreateDataset();
  const updateMutation = useUpdateDataset();

  const form = useForm<DatasetFormValues>({
    resolver: zodResolver(datasetFormSchema),
    defaultValues: { name: "", description: "" },
  });

  const open = state !== null;
  const mode = state?.mode ?? "create";
  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset({ name: "", description: "" });
      onClose();
    }
  };

  // 打开编辑对话框时回填当前值
  React.useEffect(() => {
    if (state?.mode === "edit") {
      form.reset({
        name: state.dataset.name,
        description: state.dataset.description ?? "",
      });
    }
  }, [state, form]);

  const onSubmit = form.handleSubmit(async (values) => {
    const description = values.description ? values.description : undefined;
    try {
      if (mode === "create") {
        await createMutation.mutateAsync({ name: values.name, description });
      } else if (state?.mode === "edit") {
        await updateMutation.mutateAsync({
          id: state.dataset.id,
          name: values.name,
          description: description ?? "",
        });
      }
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    form.reset({ name: "", description: "" });
    onClose();
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "新建知识库" : "编辑知识库"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "创建一个新的知识库，用于组织集合与数据。"
              : "修改知识库的名称与描述。"}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="dataset-name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="dataset-name"
              placeholder="例如：基金知识库"
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
            <Label htmlFor="dataset-description">描述</Label>
            <Textarea
              id="dataset-description"
              placeholder="可选，简要说明知识库用途"
              rows={3}
              aria-invalid={Boolean(form.formState.errors.description)}
              {...form.register("description")}
            />
            {form.formState.errors.description && (
              <p className="text-xs text-destructive">
                {form.formState.errors.description.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isPending}
            >
              取消
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2Icon className="animate-spin" />}
              {mode === "create" ? "创建" : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DatasetCard({
  dataset,
  onEdit,
  onDelete,
}: {
  dataset: Dataset;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const router = useRouter();

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => router.push(`/datasets/${dataset.id}`)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          router.push(`/datasets/${dataset.id}`);
        }
      }}
      className="group relative cursor-pointer gap-2 p-4 transition-all duration-200 outline-none hover:-translate-y-0.5 hover:shadow-md hover:ring-foreground/20 focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="absolute top-2 right-2" onClick={(e) => e.stopPropagation()}>
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="更多操作"
            className={cn(
              buttonVariants({ variant: "ghost", size: "icon-sm" }),
              "opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
            )}
          >
            <EllipsisIcon />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onEdit}>编辑</DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={onDelete}>
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="flex items-center gap-2.5">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <DatabaseIcon className="size-4" />
        </div>
        <h3 className="truncate text-sm font-medium">{dataset.name}</h3>
      </div>
      <p className="line-clamp-2 min-h-10 text-xs text-muted-foreground">
        {dataset.description ?? "暂无描述"}
      </p>
      {dataset.vectorModel && (
        <div>
          <Badge variant="secondary">{dataset.vectorModel}</Badge>
        </div>
      )}
    </Card>
  );
}

export default function DatasetsPage() {
  const [search, setSearch] = React.useState("");
  const [formState, setFormState] = React.useState<FormDialogState>(null);
  const [deleteTarget, setDeleteTarget] = React.useState<Dataset | null>(null);

  const { data: datasets, isLoading, isError, refetch } = useDatasets();
  const deleteMutation = useDeleteDataset();

  const filtered = React.useMemo(() => {
    if (!datasets) return [];
    const keyword = search.trim().toLowerCase();
    if (!keyword) return datasets;
    return datasets.filter(
      (d) =>
        d.name.toLowerCase().includes(keyword) ||
        (d.description ?? "").toLowerCase().includes(keyword)
    );
  }, [datasets, search]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    setDeleteTarget(null);
  };

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">知识库</h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索名称或描述"
              className="w-56 pl-8"
            />
          </div>
          <Button onClick={() => setFormState({ mode: "create" })}>
            <PlusIcon />
            新建知识库
          </Button>
        </div>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center gap-3 py-24 text-center">
            <p className="text-sm font-medium">加载失败</p>
            <p className="text-sm text-muted-foreground">
              无法获取知识库列表，请检查后端服务后重试。
            </p>
            <Button variant="outline" className="mt-1" onClick={() => refetch()}>
              重试
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-24 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              {datasets && datasets.length > 0 ? (
                <SearchIcon className="size-5" />
              ) : (
                <DatabaseIcon className="size-5" />
              )}
            </div>
            {datasets && datasets.length > 0 ? (
              <p className="text-sm text-muted-foreground">
                未找到匹配「{search.trim()}」的知识库
              </p>
            ) : (
              <>
                <p className="text-sm font-medium">还没有知识库</p>
                <p className="text-sm text-muted-foreground">
                  创建第一个知识库，开始组织你的数据。
                </p>
                <Button
                  variant="outline"
                  className="mt-1"
                  onClick={() => setFormState({ mode: "create" })}
                >
                  <PlusIcon />
                  新建知识库
                </Button>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((dataset) => (
              <DatasetCard
                key={dataset.id}
                dataset={dataset}
                onEdit={() => setFormState({ mode: "edit", dataset })}
                onDelete={() => setDeleteTarget(dataset)}
              />
            ))}
          </div>
        )}
      </div>

      <DatasetFormDialog state={formState} onClose={() => setFormState(null)} />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleteMutation.isPending) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除知识库</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除「{deleteTarget?.name}」吗？该操作将级联删除其下全部集合与数据，且无法恢复。
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
