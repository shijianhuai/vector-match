"use client";

import * as React from "react";
import { Loader2Icon, XIcon } from "lucide-react";
import {
  useAddMember,
  useMembers,
  useRemoveMember,
  useUpdateMemberRole,
} from "@/hooks/use-members";
import { useUserSearch } from "@/hooks/use-users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { useMe } from "@/hooks/use-auth";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { UserSearchResult } from "@/lib/api";
import type { Role } from "@/lib/types";

interface MemberPanelProps {
  datasetId: string;
  myRole: Role;
}

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "owner", label: "所有者" },
  { value: "editor", label: "编辑者" },
  { value: "viewer", label: "查看者" },
];

function RoleBadge({ role }: { role: Role }) {
  const option = ROLE_OPTIONS.find((o) => o.value === role);
  return <Badge variant="secondary">{option?.label ?? role}</Badge>;
}

export function MemberPanel({ datasetId, myRole }: MemberPanelProps) {
  const isOwner = myRole === "owner";
  const { data: me } = useMe();
  const { data: members, isLoading, isError, refetch } = useMembers(datasetId);
  const addMember = useAddMember(datasetId);
  const updateRole = useUpdateMemberRole(datasetId);
  const removeMember = useRemoveMember(datasetId);

  const [keyword, setKeyword] = React.useState("");
  const [debouncedKeyword, setDebouncedKeyword] = React.useState("");
  const [selectedUser, setSelectedUser] =
    React.useState<UserSearchResult | null>(null);
  const [dropdownOpen, setDropdownOpen] = React.useState(false);
  const [role, setRole] = React.useState<Role>("viewer");
  const [removingUserId, setRemovingUserId] = React.useState<number | null>(null);
  const comboboxRef = React.useRef<HTMLDivElement>(null);

  // 输入防抖 ~300ms
  React.useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  // 点击组件外部时收起候选下拉
  React.useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (
        comboboxRef.current &&
        !comboboxRef.current.contains(event.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const searchQuery = useUserSearch(debouncedKeyword);
  const candidates = searchQuery.data ?? [];
  const memberIds = React.useMemo(
    () => new Set(members?.map((m) => m.userId) ?? []),
    [members],
  );

  const handleKeywordChange = (value: string) => {
    setKeyword(value);
    setSelectedUser(null);
    setDropdownOpen(value.trim().length > 0);
  };

  const handleSelectUser = (user: UserSearchResult) => {
    setSelectedUser(user);
    setKeyword(user.username);
    setDropdownOpen(false);
  };

  const handleClearSelection = () => {
    setSelectedUser(null);
    setKeyword("");
    setDropdownOpen(false);
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const username = (selectedUser?.username ?? keyword).trim();
    if (!username) return;
    try {
      await addMember.mutateAsync({ username, role });
      setKeyword("");
      setSelectedUser(null);
      setDropdownOpen(false);
      setRole("viewer");
    } catch {
      // 错误已由 hook toast 处理
    }
  };

  const handleRoleChange = (userId: number, value: Role) => {
    updateRole.mutate({ userId, role: value });
  };

  const handleRemove = async () => {
    if (removingUserId === null) return;
    try {
      await removeMember.mutateAsync(removingUserId);
      setRemovingUserId(null);
    } catch {
      // 错误已由 hook toast 处理
    }
  };

  const removingMember = members?.find((m) => m.userId === removingUserId);

  return (
    <div className="space-y-4">
      {isOwner && (
        <form
          onSubmit={handleAdd}
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
        >
          <div className="grid flex-1 gap-2">
            <Label htmlFor="member-username" className="text-xs">
              用户名
            </Label>
            <div ref={comboboxRef} className="relative">
              <Input
                id="member-username"
                placeholder="输入用户名搜索并选择"
                autoComplete="off"
                value={keyword}
                onChange={(e) => handleKeywordChange(e.target.value)}
                onFocus={() => {
                  if (!selectedUser && keyword.trim()) setDropdownOpen(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setDropdownOpen(false);
                }}
                disabled={addMember.isPending}
                className={cn(selectedUser && "pr-8")}
              />
              {selectedUser && (
                <button
                  type="button"
                  aria-label="清除已选用户"
                  onClick={handleClearSelection}
                  className="absolute inset-y-0 right-0 flex w-8 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                >
                  <XIcon className="size-4" />
                </button>
              )}
              {dropdownOpen && (
                <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-lg border bg-popover shadow-[0_16px_40px_-24px_rgba(23,21,18,0.08)]">
                  {searchQuery.isLoading ? (
                    <div className="flex items-center gap-2 px-3 py-2.5 text-sm text-muted-foreground">
                      <Loader2Icon className="size-4 animate-spin" />
                      搜索中…
                    </div>
                  ) : candidates.length === 0 ? (
                    <p className="px-3 py-2.5 text-sm text-muted-foreground">
                      无匹配用户
                    </p>
                  ) : (
                    <ul className="max-h-56 overflow-y-auto p-1">
                      {candidates.map((user) => {
                        const joined = memberIds.has(user.id);
                        return (
                          <li key={user.id}>
                            <button
                              type="button"
                              disabled={joined}
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => handleSelectUser(user)}
                              className={cn(
                                "flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                                joined
                                  ? "cursor-not-allowed opacity-50"
                                  : "hover:bg-accent hover:text-accent-foreground",
                              )}
                            >
                              <span className="truncate">{user.username}</span>
                              {joined && (
                                <Badge variant="secondary">已加入</Badge>
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="grid gap-2 sm:w-32">
            <Label htmlFor="member-role" className="text-xs">
              角色
            </Label>
            <Select
              value={role}
              onValueChange={(value) => setRole(value as Role)}
              disabled={addMember.isPending}
            >
              <SelectTrigger id="member-role" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            type="submit"
            disabled={addMember.isPending || !keyword.trim()}
          >
            {addMember.isPending && (
              <Loader2Icon className="animate-spin" />
            )}
            添加
          </Button>
        </form>
      )}

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : isError ? (
        <div className="rounded-lg border bg-card py-8 text-center">
          <p className="text-sm text-destructive">加载失败</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => refetch()}
          >
            重试
          </Button>
        </div>
      ) : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户名</TableHead>
                <TableHead>角色</TableHead>
                {isOwner && <TableHead className="w-40">操作</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members?.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={isOwner ? 3 : 2}
                    className="py-8 text-center text-sm text-muted-foreground"
                  >
                    暂无成员
                  </TableCell>
                </TableRow>
              ) : (
                members?.map((member) => (
                  <TableRow key={member.userId}>
                    <TableCell className="font-medium">
                      {member.username}
                    </TableCell>
                    <TableCell>
                      {isOwner ? (
                        <Select
                          value={member.role}
                          onValueChange={(value) =>
                            handleRoleChange(member.userId, value as Role)
                          }
                          disabled={updateRole.isPending || me?.id === member.userId}
                        >
                          <SelectTrigger className="w-28">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ROLE_OPTIONS.map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <RoleBadge role={member.role} />
                      )}
                    </TableCell>
                    {isOwner && (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setRemovingUserId(member.userId)}
                          disabled={removeMember.isPending || me?.id === member.userId}
                        >
                          移除
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <AlertDialog
        open={removingUserId !== null}
        onOpenChange={(open) => {
          if (!open && !removeMember.isPending) setRemovingUserId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>移除成员</AlertDialogTitle>
            <AlertDialogDescription>
              确定要移除成员「{removingMember?.username}」吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={removeMember.isPending}>
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={removeMember.isPending}
              onClick={handleRemove}
            >
              {removeMember.isPending && (
                <Loader2Icon className="animate-spin" />
              )}
              确认移除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
