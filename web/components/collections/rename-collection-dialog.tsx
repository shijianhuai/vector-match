"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2Icon } from "lucide-react";
import { useUpdateCollection } from "@/hooks/use-collections";
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
import type { Collection } from "@/lib/types";

const renameSchema = z.object({
  name: z.string().trim().min(1, "请输入名称").max(50, "名称不能超过 50 字"),
});

type RenameFormValues = z.infer<typeof renameSchema>;

interface RenameCollectionDialogProps {
  collection: Collection | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RenameCollectionDialog({
  collection,
  open,
  onOpenChange,
}: RenameCollectionDialogProps) {
  const mutation = useUpdateCollection();
  const form = useForm<RenameFormValues>({
    resolver: zodResolver(renameSchema),
    defaultValues: {
      name: collection?.name ?? "",
    },
  });

  React.useEffect(() => {
    if (open && collection) {
      form.reset({ name: collection.name });
    }
  }, [open, collection, form]);

  const onSubmit = form.handleSubmit(async (values) => {
    if (!collection) return;
    try {
      await mutation.mutateAsync({ id: collection.id, name: values.name });
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
          <DialogTitle>重命名集合</DialogTitle>
        </DialogHeader>
        <form
          id="rename-collection-form"
          onSubmit={onSubmit}
          className="space-y-4"
        >
          <div className="grid gap-2">
            <Label htmlFor="rename-name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="rename-name"
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
            form="rename-collection-form"
            disabled={mutation.isPending}
          >
            {mutation.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
