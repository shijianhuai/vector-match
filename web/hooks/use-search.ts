"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { searchApi } from "@/lib/api";
import type { SearchRequest } from "@/lib/types";

export function useSearch(datasetId: string) {
  return useMutation({
    mutationFn: async (payload: Omit<SearchRequest, "datasetId">) => {
      const start = performance.now();
      const hits = await searchApi.search({ ...payload, datasetId });
      const duration = Math.round(performance.now() - start);
      return { hits, duration };
    },
    onError: (error: Error) => {
      toast.error(`搜索失败：${error.message}`);
    },
  });
}
