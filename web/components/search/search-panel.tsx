"use client";

import * as React from "react";
import { FileTextIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useSearch } from "@/hooks/use-search";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { SearchHit, SearchMode } from "@/lib/types";

const SEARCH_MODES: { value: SearchMode; label: string; description: string }[] = [
  {
    value: "embedding",
    label: "语义检索",
    description: "基于向量嵌入相似度召回",
  },
  {
    value: "fullTextRecall",
    label: "全文检索",
    description: "基于 jieba 全文索引召回",
  },
  {
    value: "mixedRecall",
    label: "混合检索",
    description: "向量 + 全文混合打分召回",
  },
];

function scoreBadgeClass(score: number) {
  if (score >= 0.8) {
    return "border-[#E5C4B5] bg-[#F9E9E1] text-[#B4542E]";
  }
  if (score >= 0.5) {
    return "border-[#E8E5DE] bg-[#F5F2EC] text-[#57534A]";
  }
  return "bg-muted text-muted-foreground";
}

function SearchResultCard({ hit }: { hit: SearchHit }) {
  return (
    <Card key={hit.id} className="gap-2">
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium leading-relaxed">{hit.q}</p>
            {hit.a && (
              <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
                {hit.a}
              </p>
            )}
            <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileTextIcon className="size-3.5 shrink-0" />
              <span className="truncate">{hit.sourceName}</span>
              <span className="shrink-0 text-muted-foreground/40">·</span>
              <span className="shrink-0 font-mono">
                外部 ID：{hit.keyId ?? "—"}
              </span>
            </div>
          </div>
          <Badge
            variant="outline"
            className={`shrink-0 font-mono tabular-nums ${scoreBadgeClass(hit.score)}`}
          >
            {hit.score.toFixed(3)}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function ResultSkeletons() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} className="gap-2">
          <CardContent className="pt-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-24" />
              </div>
              <Skeleton className="h-5 w-14 shrink-0 rounded-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function SearchPanel({ datasetId }: { datasetId: string }) {
  const [text, setText] = React.useState("");
  const [searchMode, setSearchMode] = React.useState<SearchMode>("embedding");
  const [topK, setTopK] = React.useState(10);
  const [similarity, setSimilarity] = React.useState(0);
  const [usingReRank, setUsingReRank] = React.useState(false);
  const [results, setResults] = React.useState<SearchHit[]>([]);
  const [duration, setDuration] = React.useState(0);
  const [hasSubmitted, setHasSubmitted] = React.useState(false);

  const search = useSearch(datasetId);

  const handleSubmit = React.useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || search.isPending) return;

    const validTopK = Math.min(100, Math.max(1, Number(topK) || 1));
    setTopK(validTopK);

    search.mutate(
      {
        text: trimmed,
        searchMode,
        topK: validTopK,
        similarity,
        usingReRank,
      },
      {
        onSuccess: ({ hits, duration: ms }) => {
          setResults(hits);
          setDuration(ms);
          setHasSubmitted(true);
        },
      }
    );
  }, [text, search, topK, searchMode, similarity, usingReRank]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTopKChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.valueAsNumber;
    setTopK(Number.isFinite(value) ? value : 1);
  };

  const handleSimilarityChange = (value: number | readonly number[]) => {
    const next = Array.isArray(value) ? value[0] : value;
    setSimilarity(Number.isFinite(next) ? next : 0);
  };

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="w-full shrink-0 space-y-4 lg:w-[400px]">
        <div className="grid gap-2">
          <Label htmlFor="search-text">查询文本</Label>
          <Textarea
            id="search-text"
            rows={4}
            placeholder="输入要测试的短文本"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <Button
          className="w-full"
          disabled={!text.trim() || search.isPending}
          onClick={handleSubmit}
        >
          {search.isPending && <Loader2Icon className="animate-spin" />}
          测试
        </Button>

        <Card className="gap-3">
          <CardHeader className="pb-1">
            <CardTitle>搜索参数</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-2">
              <Label>检索模式</Label>
              <RadioGroup
                value={searchMode}
                onValueChange={(value) => setSearchMode(value as SearchMode)}
              >
                {SEARCH_MODES.map((mode) => (
                  <Label
                    key={mode.value}
                    className="flex cursor-pointer items-start gap-3 font-normal"
                  >
                    <RadioGroupItem value={mode.value} className="mt-0.5" />
                    <div className="grid gap-0.5">
                      <span className="text-sm font-medium">{mode.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {mode.description}
                      </span>
                    </div>
                  </Label>
                ))}
              </RadioGroup>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="search-topk">召回数量（topK）</Label>
              <Input
                id="search-topk"
                type="number"
                min={1}
                max={100}
                value={topK}
                onChange={handleTopKChange}
              />
            </div>

            <div className="grid gap-3">
              <div className="flex items-center justify-between">
                <Label>最低相似度</Label>
                <span className="text-sm tabular-nums">
                  {similarity.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[similarity]}
                min={0}
                max={1}
                step={0.05}
                onValueChange={handleSimilarityChange}
              />
              <p className="text-xs text-muted-foreground">
                最低相似度阈值，0 表示不过滤
              </p>
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="search-rerank" className="cursor-pointer">
                  重排（ReRank）
                </Label>
                <Switch
                  id="search-rerank"
                  checked={usingReRank}
                  onCheckedChange={setUsingReRank}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                需服务端配置重排服务，未配置时开启会报错
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex-1">
        {!hasSubmitted ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <SearchIcon className="size-10 text-muted-foreground/50" />
            <p className="mt-4 text-sm text-muted-foreground">
              输入文本开始测试
            </p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              ⌘ / Ctrl + Enter 提交
            </p>
          </div>
        ) : search.isPending ? (
          <div className="space-y-4">
            <Skeleton className="h-4 w-48" />
            <ResultSkeletons />
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground tabular-nums">
              命中 {results.length} 条 · 耗时 {duration} ms
            </p>
            {results.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
                <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <SearchIcon className="size-5" />
                </div>
                <p className="text-sm font-medium">没有命中结果</p>
                <p className="text-sm text-muted-foreground">
                  试试降低相似度阈值，或换一种检索模式
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {results.map((hit) => (
                  <SearchResultCard key={hit.id} hit={hit} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
