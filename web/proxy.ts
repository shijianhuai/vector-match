import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const session = request.cookies.get("session")?.value;

  if (pathname.startsWith("/login") || pathname.startsWith("/register")) {
    if (session) {
      return NextResponse.redirect(new URL("/datasets", request.url));
    }
    return NextResponse.next();
  }

  if (pathname.startsWith("/datasets") || pathname.startsWith("/settings")) {
    if (!session) {
      const from = encodeURIComponent(pathname);
      return NextResponse.redirect(new URL(`/login?from=${from}`, request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/datasets/:path*",
    "/settings/:path*",
    "/login",
    "/register",
  ],
};
