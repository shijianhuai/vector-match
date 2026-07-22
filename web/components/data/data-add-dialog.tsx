"use client";

import * as React from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useQueryClient } from "@tanstack/react-query";
import { dataApi } from "@/lib/api";
import { dataKeys, usePushData } from "@/hooks/use-data";

const singleSchema = z
  .object({
    q: z.string().trim().min(1, "请输入主文本"),
    a: z.string().trim().optional(),
    keyId: z.string().trim().optional(),
    updatetime: z.string().optional(),
    indexes: z.array(z.object({ text: z.string() })).max(5),
  })
  .superRefine((values, ctx) => {
    if (values.updatetime && !values.keyId) {
      ctx.addIssue({
        code: "custom",
        path: ["updatetime"],
        message: "填写来源更新时间前请先填写外部 ID",
      });
    }
  });

type SingleFormValues = z.infer<typeof singleSchema>;

interface DataAddDialogProps {
  collectionId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DataAddDialog({
  collectionId,
  open,
  onOpenChange,
}: DataAddDialogProps) {
  const pushData = usePushData(collectionId);
  const queryClient = useQueryClient();
  const [mode, setMode] = React.useState<"single" | "batch">("single");
  const [batchText, setBatchText] = React.useState("");
  const [isBatchPending, setIsBatchPending] = React.useState(false);

  const form = useForm<SingleFormValues>({
    resolver: zodResolver(singleSchema),
    defaultValues: { q: "", a: "", keyId: "", updatetime: "", indexes: [] },
  });
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "indexes",
  });

  const parsedBatch = React.useMemo(() => {
    return batchText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const sep = line.indexOf("|");
        if (sep >= 0) {
          const q = line.slice(0, sep).trim();
          const a = line.slice(sep + 1).trim();
          return { q, a: a || undefined };
        }
        return { q: line.trim() };
      })
      .filter((item) => item.q);
  }, [batchText]);

  const batchCount = parsedBatch.length;

  const resetAll = React.useCallback(() => {
    form.reset({ q: "", a: "", keyId: "", updatetime: "", indexes: [] });
    setBatchText("");
    setMode("single");
  }, [form]);

  const handleOpenChange = (next: boolean) => {
    if (!next && !pushData.isPending && !isBatchPending) {
      resetAll();
    }
    onOpenChange(next);
  };

  const onSingleSubmit = form.handleSubmit(async (values) => {
    const indexes = (values.indexes ?? [])
      .map((i) => i.text.trim())
      .filter(Boolean)
      .map((text) => ({ text }));
    try {
      await pushData.mutateAsync({
        collectionId,
        data: [
          {
            q: values.q,
            a: values.a || undefined,
            keyId: values.keyId || undefined,
            updatetime: values.updatetime
              ? new Date(values.updatetime).toISOString()
              : undefined,
            indexes: indexes.length ? indexes : undefined,
          },
        ],
      });
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    onOpenChange(false);
  });

  const onBatchSubmit = async () => {
    if (batchCount === 0) {
      toast.error("没有可提交的数据");
      return;
    }
    setIsBatchPending(true);
    const batchSize = 200;
    let inserted = 0;
    let failed = 0;
    try {
      for (let i = 0; i < parsedBatch.length; i += batchSize) {
        const chunk = parsedBatch.slice(i, i + batchSize);
        try {
          const res = await dataApi.push({ collectionId, data: chunk });
          inserted += res.insertLen;
        } catch {
          failed += chunk.length;
        }
      }
      queryClient.invalidateQueries({ queryKey: dataKeys.all(collectionId) });
      if (failed > 0) {
        toast.error(`成功新增 ${inserted} 条，失败 ${failed} 条，请重试失败部分`);
        return;
      }
      toast.success(`成功新增 ${inserted} 条数据`);
      onOpenChange(false);
    } finally {
      setIsBatchPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>新增数据</DialogTitle>
          <DialogDescription>支持单条录入或批量粘贴</DialogDescription>
        </DialogHeader>

        <Tabs value={mode} onValueChange={(v) => setMode(v as "single" | "batch")}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="single">单条录入</TabsTrigger>
            <TabsTrigger value="batch">批量粘贴</TabsTrigger>
          </TabsList>

          <TabsContent value="single" className="space-y-4">
            <form
              id="add-single-form"
              onSubmit={onSingleSubmit}
              className="space-y-4"
            >
              <div className="grid gap-2">
                <Label htmlFor="add-q">
                  主文本 <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="add-q"
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
                <Label htmlFor="add-a">辅助文本</Label>
                <Input
                  id="add-a"
                  placeholder="例如答案或补充信息"
                  {...form.register("a")}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label htmlFor="add-key-id">外部 ID</Label>
                  <Input
                    id="add-key-id"
                    className="font-mono"
                    placeholder="如基金代码，可留空"
                    {...form.register("keyId")}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="add-updatetime">来源更新时间</Label>
                  <Input
                    id="add-updatetime"
                    type="datetime-local"
                    {...form.register("updatetime")}
                  />
                  {form.formState.errors.updatetime && (
                    <p className="text-xs text-destructive">
                      {form.formState.errors.updatetime.message}
                    </p>
                  )}
                </div>
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
          </TabsContent>

          <TabsContent value="batch" className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="batch-text">批量文本</Label>
              <Textarea
                id="batch-text"
                rows={8}
                value={batchText}
                onChange={(e) => setBatchText(e.target.value)}
                placeholder="每行一条，格式：主文本|辅助文本&#10;无竖线则仅主文本"
              />
              <p className="text-xs text-muted-foreground">
                解析后 {batchCount} 条，每批最多 200 条
              </p>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter>
          {mode === "single" ? (
            <Button
              type="submit"
              form="add-single-form"
              disabled={pushData.isPending}
            >
              {pushData.isPending && (
                <Loader2Icon className="animate-spin" />
              )}
              提交
            </Button>
          ) : (
            <Button
              type="button"
              onClick={onBatchSubmit}
              disabled={isBatchPending || batchCount === 0}
            >
              {isBatchPending && (
                <Loader2Icon className="animate-spin" />
              )}
              提交
              {batchCount > 0 && `（${batchCount} 条）`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
