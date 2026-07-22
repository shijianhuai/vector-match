"use client";

import * as React from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useDataDetail, useUpdateData } from "@/hooks/use-data";

const editSchema = z.object({
  q: z.string().trim().min(1, "请输入主文本"),
  a: z.string().trim().optional(),
  indexes: z.array(z.object({ text: z.string() })).max(5),
});

type EditFormValues = z.infer<typeof editSchema>;

function formatSourceTime(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

interface DataEditDialogProps {
  collectionId: string;
  dataId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DataEditDialog({
  collectionId,
  dataId,
  open,
  onOpenChange,
}: DataEditDialogProps) {
  const updateData = useUpdateData(collectionId);
  const { data, isLoading } = useDataDetail(dataId ?? "");

  const form = useForm<EditFormValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { q: "", a: "", indexes: [] },
  });
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "indexes",
  });

  React.useEffect(() => {
    if (data) {
      form.reset({
        q: data.q,
        a: data.a ?? "",
        indexes: data.indexes.map((i) => ({ text: i.text })),
      });
    }
  }, [data, form]);

  const handleOpenChange = (next: boolean) => {
    if (!next && !updateData.isPending) {
      form.reset({ q: "", a: "", indexes: [] });
    }
    onOpenChange(next);
  };

  const onSubmit = form.handleSubmit(async (values) => {
    if (!dataId) return;
    const indexes = (values.indexes ?? [])
      .map((i) => i.text.trim())
      .filter(Boolean)
      .map((text) => ({ text }));
    try {
      await updateData.mutateAsync({
        dataId,
        q: values.q,
        // 空串即清空（后端 a="" 会落库；undefined 则跳过不更新）
        a: values.a ?? "",
        indexes: indexes.length ? indexes : undefined,
      });
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    onOpenChange(false);
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>编辑数据</DialogTitle>
          <DialogDescription>修改主文本、辅助文本或自定义索引</DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-4 py-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : (
          <form id="edit-data-form" onSubmit={onSubmit} className="space-y-4">
            <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              <span>
                外部 ID：
                <span className="font-mono text-foreground">
                  {data?.keyId ?? "—"}
                </span>
              </span>
              <span>
                来源更新时间：
                <span className="text-foreground">
                  {formatSourceTime(data?.sourceUpdatetime)}
                </span>
              </span>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="edit-q">
                主文本 <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="edit-q"
                rows={3}
                placeholder="例如问题或主关键词"
                {...form.register("q")}
              />
              {form.formState.errors.q && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.q.message}
                </p>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="edit-a">辅助文本</Label>
              <Input
                id="edit-a"
                placeholder="例如答案或补充信息"
                {...form.register("a")}
              />
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>自定义索引</Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={() => append({ text: "" })}
                  disabled={fields.length >= 5}
                >
                  <PlusIcon className="size-3.5" />
                  添加
                </Button>
              </div>
              {fields.map((field, index) => (
                <div key={field.id} className="flex items-center gap-2">
                  <Input
                    placeholder={`索引 ${index + 1}`}
                    {...form.register(`indexes.${index}.text`)}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => remove(index)}
                  >
                    <Trash2Icon className="size-3.5" />
                  </Button>
                </div>
              ))}
              {fields.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  最多添加 5 条自定义索引
                </p>
              )}
            </div>
          </form>
        )}

        <DialogFooter>
          <Button
            type="submit"
            form="edit-data-form"
            disabled={updateData.isPending || isLoading}
          >
            {updateData.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
