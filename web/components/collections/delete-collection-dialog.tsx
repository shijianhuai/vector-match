"use client";

import * as React from "react";
import { Loader2Icon } from "lucide-react";
import { useDeleteCollections } from "@/hooks/use-collections";
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

interface DeleteCollectionDialogProps {
  ids: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export function DeleteCollectionDialog({
  ids,
  open,
  onOpenChange,
  onSuccess,
}: DeleteCollectionDialogProps) {
  const mutation = useDeleteCollections();

  const handleDelete = async () => {
    try {
      await mutation.mutateAsync(ids);
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    onOpenChange(false);
    onSuccess?.();
  };

  return (
    <AlertDialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !mutation.isPending) {
          onOpenChange(false);
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除集合</AlertDialogTitle>
          <AlertDialogDescription>
            确定要删除 <strong>{ids.length}</strong> 个集合吗？该操作将级联删除其下全部子集合与数据，且无法恢复。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>
            取消
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={mutation.isPending}
            onClick={handleDelete}
          >
            {mutation.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            确认删除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
