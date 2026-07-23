"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileTextIcon,
  FolderIcon,
  MoreHorizontalIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react";
import {
  useCollectionAncestors,
  useCollections,
  type CollectionAncestor,
} from "@/hooks/use-collections";
import { useDataset } from "@/hooks/use-datasets";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { CreateCollectionDialog } from "./create-collection-dialog";
import { RenameCollectionDialog } from "./rename-collection-dialog";
import { DeleteCollectionDialog } from "./delete-collection-dialog";
import type { Collection } from "@/lib/types";

const PAGE_SIZE = 20;

interface CollectionBrowserProps {
  datasetId: string;
  parentId: string | null;
}

export function CollectionBrowser({
  datasetId,
  parentId,
}: CollectionBrowserProps) {
  const router = useRouter();
  const basePath = `/datasets/${datasetId}/collections`;

  const { data: dataset } = useDataset(datasetId);
  const myRole = dataset?.myRole ?? "viewer";
  const canEdit = myRole === "owner";

  const [offset, setOffset] = React.useState(0);
  const [searchText, setSearchText] = React.useState("");
  const [inputValue, setInputValue] = React.useState("");
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(
    new Set()
  );
  const [createOpen, setCreateOpen] = React.useState(false);
  const [renameCollection, setRenameCollection] = React.useState<
    Collection | null
  >(null);
  const [deleteIds, setDeleteIds] = React.useState<string[]>([]);

  const collectionsQuery = useCollections({
    datasetId,
    parentId,
    offset,
    pageSize: PAGE_SIZE,
    searchText,
  });
  const ancestorsQuery = useCollectionAncestors(parentId);

  const list = collectionsQuery.data?.list ?? [];
  const total = collectionsQuery.data?.total ?? 0;

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setSearchText(inputValue);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const toggleSelection = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const allSelected =
    list.length > 0 && list.every((item) => selectedIds.has(item.id));
  const someSelected =
    list.some((item) => selectedIds.has(item.id)) && !allSelected;

  const toggleAll = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        list.forEach((item) => next.delete(item.id));
      } else {
        list.forEach((item) => next.add(item.id));
      }
      return next;
    });
  };

  const handleRowClick = (collection: Collection) => {
    if (collection.type === "folder") {
      router.push(
        `${basePath}?parentId=${encodeURIComponent(collection.id)}`
      );
    } else {
      router.push(
        `/datasets/${datasetId}/data?collectionId=${encodeURIComponent(
          collection.id
        )}`
      );
    }
  };

  const handleDeleteSuccess = () => {
    const removedIds = deleteIds;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      removedIds.forEach((id) => next.delete(id));
      return next;
    });
    setDeleteIds([]);
  };

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  // 删除末页最后几项后 offset 越界时，渲染期回退到最后一页（React 认可的 adjust-state-during-render 模式）
  if (total > 0 && offset >= total) {
    setOffset(Math.max(0, (Math.ceil(total / PAGE_SIZE) - 1) * PAGE_SIZE));
  }

  return (
    <div className="space-y-4">
      <CollectionBreadcrumb
        datasetId={datasetId}
        parentId={parentId}
        ancestors={ancestorsQuery.data ?? []}
        isLoading={ancestorsQuery.isLoading}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {canEdit ? (
          <Button onClick={() => setCreateOpen(true)}>
            <PlusIcon />
            新建集合
          </Button>
        ) : (
          <div />
        )}
        <div className="relative w-full sm:w-64">
          <SearchIcon className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索集合名称"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {collectionsQuery.isLoading ? (
        <CollectionSkeleton />
      ) : collectionsQuery.isError ? (
        <div className="rounded-lg border bg-card py-12 text-center">
          <p className="text-sm text-destructive">
            加载失败，请稍后重试
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => collectionsQuery.refetch()}
          >
            重试
          </Button>
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          searchText={searchText}
          canEdit={canEdit}
          onCreate={() => setCreateOpen(true)}
        />
      ) : (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  {canEdit && (
                    <TableHead className="w-10">
                      <Checkbox
                        checked={allSelected}
                        indeterminate={someSelected}
                        onCheckedChange={toggleAll}
                        aria-label="全选"
                      />
                    </TableHead>
                  )}
                  <TableHead>名称</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="w-20">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.map((collection) => (
                  <TableRow
                    key={collection.id}
                    className="cursor-pointer"
                    onClick={() => handleRowClick(collection)}
                  >
                    {canEdit && (
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.has(collection.id)}
                          onCheckedChange={() =>
                            toggleSelection(collection.id)
                          }
                          aria-label={`选择 ${collection.name}`}
                        />
                      </TableCell>
                    )}
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {collection.type === "folder" ? (
                          <FolderIcon className="size-4 text-muted-foreground" />
                        ) : (
                          <FileTextIcon className="size-4 text-muted-foreground" />
                        )}
                        <span className="font-medium">{collection.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          collection.type === "folder"
                            ? "secondary"
                            : "default"
                        }
                      >
                        {collection.type === "folder"
                          ? "文件夹"
                          : "数据集合"}
                      </Badge>
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {canEdit && (
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            render={
                              <Button
                                variant="ghost"
                                size="icon-xs"
                                aria-label="操作"
                              >
                                <MoreHorizontalIcon />
                              </Button>
                            }
                          />
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() =>
                                setRenameCollection(collection)
                              }
                            >
                              重命名
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() =>
                                setDeleteIds([collection.id])
                              }
                            >
                              删除
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm">
            <div className="text-muted-foreground tabular-nums">
              第 {currentPage} 页 / 共 {total} 条
            </div>
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
                onClick={() =>
                  setOffset((prev) => prev + PAGE_SIZE)
                }
                disabled={!hasNext}
              >
                下一页
              </Button>
            </div>
          </div>
        </>
      )}

      {canEdit && selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 z-40 w-full max-w-md -translate-x-1/2 px-4">
          <Card className="flex items-center justify-between gap-4 p-4 shadow-[0_20px_50px_-24px_rgba(23,21,18,0.08)]">
            <span className="text-sm">
              已选 <strong>{selectedIds.size}</strong> 项
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedIds(new Set())}
              >
                取消
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() =>
                  setDeleteIds(Array.from(selectedIds))
                }
              >
                <Trash2Icon />
                批量删除
              </Button>
            </div>
          </Card>
        </div>
      )}

      <CreateCollectionDialog
        datasetId={datasetId}
        parentId={parentId}
        open={createOpen}
        onOpenChange={setCreateOpen}
      />

      <RenameCollectionDialog
        collection={renameCollection}
        open={Boolean(renameCollection)}
        onOpenChange={(open) => {
          if (!open) setRenameCollection(null);
        }}
      />

      <DeleteCollectionDialog
        ids={deleteIds}
        open={deleteIds.length > 0}
        onOpenChange={(open) => {
          if (!open) setDeleteIds([]);
        }}
        onSuccess={handleDeleteSuccess}
      />
    </div>
  );
}

function CollectionBreadcrumb({
  datasetId,
  parentId,
  ancestors,
  isLoading,
}: {
  datasetId: string;
  parentId: string | null;
  ancestors: CollectionAncestor[];
  isLoading: boolean;
}) {
  const basePath = `/datasets/${datasetId}/collections`;

  if (isLoading) {
    return <Skeleton className="h-5 w-48" />;
  }

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          {parentId ? (
            <BreadcrumbLink
              render={<Link href={basePath}>全部</Link>}
            />
          ) : (
            <BreadcrumbPage>全部</BreadcrumbPage>
          )}
        </BreadcrumbItem>
        {ancestors.map((item, index) => {
          const isLast = index === ancestors.length - 1;
          return (
            <React.Fragment key={item.id}>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {isLast ? (
                  <BreadcrumbPage>{item.name}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink
                    render={
                      <Link
                        href={`${basePath}?parentId=${encodeURIComponent(
                          item.id
                        )}`}
                      >
                        {item.name}
                      </Link>
                    }
                  />
                )}
              </BreadcrumbItem>
            </React.Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

function CollectionSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

function EmptyState({
  searchText,
  canEdit,
  onCreate,
}: {
  searchText: string;
  canEdit: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border bg-card py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {searchText ? (
          <SearchIcon className="size-5" />
        ) : (
          <FolderIcon className="size-5" />
        )}
      </div>
      {searchText ? (
        <p className="text-sm font-medium">
          未找到与「{searchText}」相关的集合
        </p>
      ) : (
        <>
          <p className="text-sm font-medium">暂无集合</p>
          <p className="text-sm text-muted-foreground">
            {canEdit
              ? "创建集合后，就可以向其中添加数据"
              : "该知识库下还没有任何集合"}
          </p>
        </>
      )}
      {!searchText && canEdit && (
        <Button className="mt-1" onClick={onCreate}>
          <PlusIcon />
          新建集合
        </Button>
      )}
    </div>
  );
}
