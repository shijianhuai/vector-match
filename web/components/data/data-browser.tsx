"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  Loader2Icon,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react";
import { collectionApi } from "@/lib/api";
import { collectionKeys } from "@/hooks/use-collections";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useDataList } from "@/hooks/use-data";
import { useDataset } from "@/hooks/use-datasets";
import { DataAddDialog } from "./data-add-dialog";
import { DataEditDialog } from "./data-edit-dialog";
import { DataDeleteDialog } from "./data-delete-dialog";
import type { DataItem } from "@/lib/types";

interface DataBrowserProps {
  datasetId: string;
  collectionId: string;
}

export function DataBrowser({ datasetId, collectionId }: DataBrowserProps) {
  const router = useRouter();
  const collectionsPath = `/datasets/${datasetId}/collections`;

  const { data: dataset } = useDataset(datasetId);
  const myRole = dataset?.myRole ?? "viewer";
  const canEdit = myRole === "owner" || myRole === "editor";

  const {
    data: collection,
    isLoading: isLoadingCollection,
    isError: isCollectionError,
  } = useQuery({
    queryKey: collectionKeys.detail(collectionId),
    queryFn: () => collectionApi.detail(collectionId),
    enabled: Boolean(collectionId),
  });

  React.useEffect(() => {
    if (
      !isLoadingCollection &&
      (isCollectionError || collection?.type === "folder")
    ) {
      router.replace(collectionsPath);
    }
  }, [isLoadingCollection, isCollectionError, collection, router, collectionsPath]);

  const [searchText, setSearchText] = React.useState("");
  const [debouncedSearchText, setDebouncedSearchText] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [pageSize, setPageSize] = React.useState(20);
  const [addOpen, setAddOpen] = React.useState(false);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [deletingItem, setDeletingItem] = React.useState<DataItem | null>(null);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchText(searchText);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  const clampedPageSize = Math.min(100, Math.max(1, pageSize));

  const handlePageSizeChange = (value: number) => {
    const normalized = Number.isNaN(value) ? 20 : value;
    const clamped = Math.min(100, Math.max(1, normalized));
    setPageSize(clamped);
    setOffset(0);
  };

  const { data, isLoading: isLoadingData } = useDataList({
    collectionId,
    offset,
    pageSize: clampedPageSize,
    searchText: debouncedSearchText,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / clampedPageSize));
  const currentPage = Math.min(
    totalPages,
    Math.floor(offset / clampedPageSize) + 1
  );

  // 删除末页最后几项后 offset 越界时，渲染期回退到最后一页（React 认可的 adjust-state-during-render 模式）
  if (total > 0 && offset >= total) {
    setOffset((totalPages - 1) * clampedPageSize);
  }

  const handlePrev = () => {
    setOffset((prev) => Math.max(0, prev - clampedPageSize));
  };

  const handleNext = () => {
    setOffset((prev) =>
      Math.min((totalPages - 1) * clampedPageSize, prev + clampedPageSize)
    );
  };

  if (isLoadingCollection) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-6 w-48" />
        </div>
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            href={collectionsPath}
            className="inline-flex shrink-0 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeftIcon className="size-4" />
            集合
          </Link>
          <span className="text-muted-foreground/40">/</span>
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {collection?.name ?? "数据管理"}
          </h1>
        </div>

        {canEdit && (
          <Button onClick={() => setAddOpen(true)}>
            <PlusIcon className="size-4" />
            新增数据
          </Button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <SearchIcon className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="搜索主文本或辅助文本..."
            className="pl-9"
          />
        </div>
      </div>

      {isLoadingData ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : total === 0 ? (
        debouncedSearchText ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-16 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <SearchIcon className="size-5" />
            </div>
            <p className="text-sm font-medium">未找到相关数据</p>
            <p className="text-sm text-muted-foreground">
              未找到包含「{debouncedSearchText}」的数据
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-16 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <PlusIcon className="size-5" />
            </div>
            <p className="text-sm font-medium">暂无数据</p>
            <p className="text-sm text-muted-foreground">
              点击右上角新增数据，或批量粘贴导入
            </p>
            {canEdit && (
              <Button className="mt-1" onClick={() => setAddOpen(true)}>
                <PlusIcon className="size-4" />
                新增数据
              </Button>
            )}
          </div>
        )
      ) : (
        <div className="divide-y rounded-lg border">
          {data?.list.map((item) => (
            <div
              key={item.id}
              className="group relative flex items-start justify-between gap-4 px-3 py-3 even:bg-muted/50 hover:bg-muted/80"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <p className="truncate font-medium text-foreground">
                    {item.q}
                  </p>
                  <span className="shrink-0 font-mono text-xs text-muted-foreground/70">
                    外部 ID：{item.keyId ?? "—"}
                  </span>
                </div>
                {item.a && (
                  <p className="mt-1 truncate text-sm text-muted-foreground">
                    {item.a}
                  </p>
                )}
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <Badge
                  variant="outline"
                  className={
                    item.trained
                      ? "border-[#A3D9A5] bg-[#E6F7E6] text-[#2D6A2D]"
                      : "border-border bg-muted text-muted-foreground"
                  }
                >
                  {item.trained ? (
                    "已训练"
                  ) : (
                    <span className="flex items-center gap-1">
                      待训练
                      <Loader2Icon className="size-3 animate-spin" />
                    </span>
                  )}
                </Badge>

                <div className="flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100">
                  {canEdit && (
                    <>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        aria-label="编辑"
                        onClick={() => setEditingId(item.id)}
                      >
                        <PencilIcon className="size-3.5" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-destructive hover:text-destructive"
                        aria-label="删除"
                        onClick={() => setDeletingItem(item)}
                      >
                        <Trash2Icon className="size-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {total > 0 && (
        <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">每页</span>
            <Input
              type="number"
              min={1}
              max={100}
              value={pageSize}
              onChange={(e) => handlePageSizeChange(Number(e.target.value))}
              className="h-8 w-20"
            />
            <span className="text-sm text-muted-foreground">条</span>
          </div>

          <p className="text-sm text-muted-foreground tabular-nums">
            第 {currentPage} 页 / 共 {total} 条
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrev}
              disabled={offset === 0}
            >
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNext}
              disabled={offset + clampedPageSize >= total}
            >
              下一页
            </Button>
          </div>
        </div>
      )}

      <DataAddDialog
        collectionId={collectionId}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      <DataEditDialog
        collectionId={collectionId}
        dataId={editingId}
        open={Boolean(editingId)}
        onOpenChange={(open) => {
          if (!open) setEditingId(null);
        }}
      />

      <DataDeleteDialog
        collectionId={collectionId}
        dataId={deletingItem?.id ?? null}
        dataQ={deletingItem?.q ?? ""}
        open={Boolean(deletingItem)}
        onOpenChange={(open) => {
          if (!open) setDeletingItem(null);
        }}
      />
    </div>
  );
}
