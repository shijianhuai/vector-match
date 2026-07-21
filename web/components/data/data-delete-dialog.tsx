"use client";

import * as React from "react";
import { Loader2Icon } from "lucide-react";
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
import { useDeleteData } from "@/hooks/use-data";

interface DataDeleteDialogProps {
  collectionId: string;
  dataId: string | null;
  dataQ: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DataDeleteDialog({
  collectionId,
  dataId,
  dataQ,
  open,
  onOpenChange,
}: DataDeleteDialogProps) {
  const deleteData = useDeleteData(collectionId);

  const handleOpenChange = (next: boolean) => {
    if (!next && !deleteData.isPending) {
      onOpenChange(false);
    }
  };

  const handleConfirm = async () => {
    if (!dataId) return;
    try {
      await deleteData.mutateAsync(dataId);
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除数据</AlertDialogTitle>
          <AlertDialogDescription>
            确定要删除这条数据吗？该操作将触发索引重建，且无法恢复。
            {dataQ && (
              <span className="mt-1 block truncate font-medium text-foreground">
                「{dataQ}」
              </span>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleteData.isPending}>取消</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={deleteData.isPending}
            onClick={handleConfirm}
          >
            {deleteData.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            确认删除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
