"use client";

import { useRouter } from "next/navigation";
import { LogOutIcon, SettingsIcon, UserIcon } from "lucide-react";
import { useMe, useLogout } from "@/hooks/use-auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface UserMenuProps {
  menuSide?: "top" | "bottom" | "left" | "right";
  menuAlign?: "start" | "center" | "end";
  className?: string;
}

export function UserMenu({ menuSide = "bottom", menuAlign = "end", className }: UserMenuProps = {}) {
  const { data: user } = useMe();
  const logout = useLogout();
  const router = useRouter();

  if (!user) return null;

  const initials = user.username.slice(0, 2).toUpperCase();

  const handleLogout = async () => {
    await logout.mutateAsync();
    router.push("/login");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={cn("inline-flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}>
        <Avatar size="sm">
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <span className="hidden sm:inline">{user.username}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent side={menuSide} align={menuAlign} className="min-w-48">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex items-center gap-2 font-normal">
            <UserIcon className="size-4 shrink-0 text-muted-foreground" />
            <span className="flex min-w-0 flex-col">
              <span className="truncate font-medium">{user.username}</span>
              {user.email && (
                <span className="truncate text-xs text-muted-foreground">
                  {user.email}
                </span>
              )}
            </span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {user.isSuperuser && (
            <DropdownMenuItem onClick={() => router.push("/settings/users")}>
              <SettingsIcon className="size-4" />
              用户管理
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onClick={handleLogout}>
            <LogOutIcon className="size-4" />
            退出登录
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
