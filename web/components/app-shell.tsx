"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DatabaseIcon, UsersIcon, WaypointsIcon } from "lucide-react";
import { useMe } from "@/hooks/use-auth";
import { UserMenu } from "@/components/user-menu";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  superuserOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/datasets", label: "知识库", icon: DatabaseIcon },
  { href: "/settings/users", label: "用户管理", icon: UsersIcon, superuserOnly: true },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      href="/datasets"
      className="flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <WaypointsIcon className="size-4" />
      </span>
      {!compact && (
        <span className="text-base font-semibold tracking-tight">
          Vector Match
        </span>
      )}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: me } = useMe();

  const items = NAV_ITEMS.filter((item) => !item.superuserOnly || me?.isSuperuser);

  return (
    <div className="flex flex-1 items-stretch">
      {/* 桌面端侧边栏 */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
        <div className="px-4 py-5">
          <BrandMark />
        </div>

        <nav className="flex-1 space-y-1 px-3">
          <p className="px-2 pb-1.5 text-xs font-medium text-muted-foreground">
            导航
          </p>
          {items.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors duration-150",
                  active
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                )}
              >
                <item.icon className="size-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-sidebar-border p-3">
          <UserMenu menuSide="top" menuAlign="start" className="w-full justify-start" />
        </div>
      </aside>

      {/* 内容区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 移动端顶栏 */}
        <header className="sticky top-0 z-40 flex items-center gap-1 border-b bg-background/95 px-3 py-2 backdrop-blur md:hidden">
          <BrandMark compact />
          <nav className="flex flex-1 items-center justify-center gap-1">
            {items.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition-colors duration-150",
                    active
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                  )}
                >
                  <item.icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <UserMenu />
        </header>

        <main className="flex flex-1 flex-col">{children}</main>
      </div>
    </div>
  );
}
