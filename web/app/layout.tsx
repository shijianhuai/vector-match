import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { QueryProvider } from "@/components/providers/query-provider";
import { Toaster } from "@/components/ui/sonner";
import { UserMenu } from "@/components/user-menu";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vector Match",
  description: "知识库管理",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <QueryProvider>
          <header className="sticky top-0 z-50 border-b bg-background px-6 py-3">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
              <Link href="/datasets" className="text-lg font-semibold tracking-tight">
                Vector Match
              </Link>
              <UserMenu />
            </div>
          </header>
          <main className="flex flex-1 flex-col">{children}</main>
          <Toaster />
        </QueryProvider>
      </body>
    </html>
  );
}
