"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { ArrowLeftIcon } from "lucide-react";
import { useDataset } from "@/hooks/use-datasets";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TABS = [
  { segment: "collections", label: "集合" },
  { segment: "search", label: "搜索测试" },
  { segment: "settings", label: "设置" },
] as const;

export default function DatasetLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { datasetId } = useParams<{ datasetId: string }>();
  const pathname = usePathname();
  const { data: dataset, isLoading, isError } = useDataset(datasetId);

  const basePath = `/datasets/${datasetId}`;

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-6">
      <div className="flex items-center gap-3">
        <Link
          href="/datasets"
          className="inline-flex shrink-0 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          返回列表
        </Link>
        <span className="text-muted-foreground/40">/</span>
        {isLoading ? (
          <Skeleton className="h-6 w-40" />
        ) : (
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {dataset?.name ?? "知识库"}
          </h1>
        )}
      </div>

      {isError ? (
        <div className="flex flex-col items-center gap-3 py-24 text-center">
          <p className="text-sm font-medium">知识库不存在或已删除</p>
          <Link
            href="/datasets"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeftIcon className="size-4" />
            返回列表
          </Link>
        </div>
      ) : (
        <>
          <nav className="mt-4 flex gap-1 border-b">
            {TABS.map((tab) => {
              const href = `${basePath}/${tab.segment}`;
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={tab.segment}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative -mb-px px-3 py-2 text-sm transition-colors duration-200",
                    active
                      ? "font-medium text-foreground after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-[#D9552C]"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
          <div className="py-6">{children}</div>
        </>
      )}
    </div>
  );
}
