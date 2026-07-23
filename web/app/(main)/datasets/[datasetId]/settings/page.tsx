"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { CheckIcon, CopyIcon, Loader2Icon } from "lucide-react";
import { useMe } from "@/hooks/use-auth";
import {
  useDataset,
  useDeleteDataset,
  useUpdateDataset,
} from "@/hooks/use-datasets";
import { MemberPanel } from "@/components/members/member-panel";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
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
import { cn } from "@/lib/utils";

const settingsFormSchema = z.object({
  name: z.string().trim().min(1, "请输入名称").max(50, "名称不能超过 50 字"),
  description: z
    .string()
    .trim()
    .max(200, "描述不能超过 200 字")
    .optional(),
});

type SettingsFormValues = z.infer<typeof settingsFormSchema>;

const SECTIONS = [
  { id: "general", label: "基本设置" },
  { id: "info", label: "信息" },
  { id: "members", label: "成员管理" },
  { id: "danger", label: "危险区", ownerOnly: true },
] as const;

export default function DatasetSettingsPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const router = useRouter();

  const { data: dataset, isLoading } = useDataset(datasetId);
  const updateMutation = useUpdateDataset();
  const deleteMutation = useDeleteDataset();

  const { data: me } = useMe();
  const myRole = dataset?.myRole ?? "viewer";
  const canEdit = myRole === "owner";
  const canDelete =
    canEdit && (me?.role === "superadmin" || dataset?.creatorId === me?.id);

  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const visibleSections = SECTIONS.filter(
    (section) => !("ownerOnly" in section && section.ownerOnly) || canDelete,
  );

  const [activeSection, setActiveSection] = React.useState<string>(
    visibleSections[0].id,
  );

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveSection(entry.target.id);
        }
      },
      { rootMargin: "-25% 0px -65% 0px" },
    );
    for (const section of visibleSections) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canDelete, isLoading]);

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsFormSchema),
    values: {
      name: dataset?.name ?? "",
      description: dataset?.description ?? "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await updateMutation.mutateAsync({
        id: datasetId,
        name: values.name,
        description: values.description ?? "",
      });
    } catch {
      // 错误已由 hook toast 处理
    }
  });

  const handleCopyId = async () => {
    if (!dataset) return;
    try {
      await navigator.clipboard.writeText(dataset.id);
      setCopied(true);
      toast.success("已复制数据集 ID");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(datasetId);
    } catch {
      // 错误已由 hook toast 处理，保持对话框打开
      return;
    }
    setDeleteOpen(false);
    router.push("/datasets");
  };

  if (isLoading) {
    return (
      <div className="grid gap-8 lg:grid-cols-[180px_minmax(0,1fr)]">
        <div className="hidden space-y-2 lg:block">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
        <div className="max-w-2xl space-y-6">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      </div>
    );
  }

  const sectionNav = (className?: string) => (
    <nav aria-label="设置分区" className={className}>
      {visibleSections.map((section) => {
        const active = activeSection === section.id;
        const isDanger = section.id === "danger";
        return (
          <a
            key={section.id}
            href={`#${section.id}`}
            aria-current={active ? "true" : undefined}
            className={cn(
              "block rounded-lg px-2.5 py-1.5 text-sm transition-colors duration-150",
              active
                ? "bg-accent font-medium text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
              isDanger && !active && "text-destructive/80 hover:text-destructive",
              isDanger && active && "bg-destructive/10 text-destructive",
            )}
          >
            {section.label}
          </a>
        );
      })}
    </nav>
  );

  return (
    <div className="grid gap-8 lg:grid-cols-[180px_minmax(0,1fr)]">
      {/* 桌面端锚点导航 */}
      <div className="hidden lg:block">
        <div className="sticky top-8">{sectionNav("space-y-1")}</div>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* 移动端锚点导航 */}
        {sectionNav("flex flex-wrap gap-1 lg:hidden")}

        <Card id="general" className="scroll-mt-20">
          <CardHeader>
            <CardTitle>基本设置</CardTitle>
            <CardDescription>知识库的名称与描述信息。</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="settings-name">
                  名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="settings-name"
                  disabled={!canEdit}
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
                <Label htmlFor="settings-description">描述</Label>
                <Textarea
                  id="settings-description"
                  rows={3}
                  disabled={!canEdit}
                  placeholder="可选，简要说明知识库用途"
                  aria-invalid={Boolean(form.formState.errors.description)}
                  {...form.register("description")}
                />
                {form.formState.errors.description && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.description.message}
                  </p>
                )}
              </div>
              {canEdit && (
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending && (
                    <Loader2Icon className="animate-spin" />
                  )}
                  保存
                </Button>
              )}
            </form>
          </CardContent>
        </Card>

        <Card id="info" className="scroll-mt-20">
          <CardHeader>
            <CardTitle>信息</CardTitle>
            <CardDescription>该知识库的只读属性。</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <dt className="w-20 shrink-0 text-muted-foreground">数据集 ID</dt>
                <dd className="flex min-w-0 items-center gap-1.5">
                  <code className="truncate rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                    {dataset?.id}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    aria-label="复制数据集 ID"
                    onClick={handleCopyId}
                  >
                    {copied ? <CheckIcon /> : <CopyIcon />}
                  </Button>
                </dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="w-20 shrink-0 text-muted-foreground">向量模型</dt>
                <dd>{dataset?.vectorModel ?? "—"}</dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="w-20 shrink-0 text-muted-foreground">我的角色</dt>
                <dd>{myRole}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card id="members" className="scroll-mt-20">
          <CardHeader>
            <CardTitle>成员管理</CardTitle>
            <CardDescription>
              管理可访问该知识库的成员及其角色。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MemberPanel datasetId={datasetId} myRole={myRole} />
          </CardContent>
        </Card>

        {canDelete && (
          <Card
            id="danger"
            className="scroll-mt-20 bg-destructive/[0.04] ring-destructive/40"
          >
            <CardHeader>
              <CardTitle className="text-destructive">危险区</CardTitle>
              <CardDescription>
                删除知识库将级联删除其下全部集合与数据，该操作无法恢复。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="destructive"
                onClick={() => setDeleteOpen(true)}
              >
                删除知识库
              </Button>
            </CardContent>
          </Card>
        )}

        <AlertDialog
          open={deleteOpen}
          onOpenChange={(open) => {
            if (!open && !deleteMutation.isPending) setDeleteOpen(false);
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>删除知识库</AlertDialogTitle>
              <AlertDialogDescription>
                确定要删除「{dataset?.name}」吗？该操作将级联删除其下全部集合与数据，且无法恢复。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteMutation.isPending}>
                取消
              </AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={handleDelete}
              >
                {deleteMutation.isPending && (
                  <Loader2Icon className="animate-spin" />
                )}
                确认删除
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}
