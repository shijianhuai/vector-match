"use client";

import * as React from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2Icon } from "lucide-react";
import { useCreateCollection } from "@/hooks/use-collections";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { CollectionType } from "@/lib/types";

const createSchema = z.object({
  name: z.string().trim().min(1, "请输入名称").max(50, "名称不能超过 50 字"),
  type: z.enum(["folder", "virtual"]),
});

type CreateFormValues = z.infer<typeof createSchema>;

interface CreateCollectionDialogProps {
  datasetId: string;
  parentId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateCollectionDialog({
  datasetId,
  parentId,
  open,
  onOpenChange,
}: CreateCollectionDialogProps) {
  const mutation = useCreateCollection();
  const form = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: "",
      type: "virtual",
    },
  });

  React.useEffect(() => {
    if (open) {
      form.reset({ name: "", type: "virtual" });
    }
  }, [open, form]);

  const typeValue = useWatch({ control: form.control, name: "type" });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await mutation.mutateAsync({
        datasetId,
        parentId: parentId ?? undefined,
        name: values.name,
        type: values.type as CollectionType,
      });
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    onOpenChange(false);
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>新建集合</DialogTitle>
        </DialogHeader>
        <form
          id="create-collection-form"
          onSubmit={onSubmit}
          className="space-y-4"
        >
          <div className="grid gap-2">
            <Label htmlFor="create-name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="create-name"
              placeholder="请输入集合名称"
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
            <Label>类型</Label>
            <RadioGroup
              value={typeValue}
              onValueChange={(value) =>
                form.setValue("type", value as CreateFormValues["type"], {
                  shouldValidate: true,
                })
              }
              className="flex flex-col gap-2"
            >
              <Label className="flex cursor-pointer items-center gap-2 font-normal">
                <RadioGroupItem value="virtual" />
                数据集合
              </Label>
              <Label className="flex cursor-pointer items-center gap-2 font-normal">
                <RadioGroupItem value="folder" />
                文件夹
              </Label>
            </RadioGroup>
          </div>
        </form>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            取消
          </Button>
          <Button
            type="submit"
            form="create-collection-form"
            disabled={mutation.isPending}
          >
            {mutation.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
