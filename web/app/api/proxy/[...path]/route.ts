import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxyHandler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const segments = path.map((segment) => encodeURIComponent(segment)).join("/");
  const targetUrl = `${BACKEND_URL}/api/${segments}${req.nextUrl.search}`;

  const headers: Record<string, string> = {};
  const session = req.cookies.get("session")?.value;
  if (session) {
    headers.Authorization = `Bearer ${session}`;
  }

  if (req.headers.get("content-type")?.includes("application/json")) {
    headers["Content-Type"] = "application/json";
  }

  let body: string | undefined;
  if (
    req.method !== "GET" &&
    req.method !== "HEAD" &&
    req.headers.get("content-type")?.includes("application/json")
  ) {
    const text = await req.text();
    if (text) body = text;
  }

  try {
    const backendRes = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });
    const resBody = await backendRes.text();
    return new NextResponse(resBody, {
      status: backendRes.status,
      headers: {
        "Content-Type": backendRes.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "backend unavailable" },
      { status: 502 },
    );
  }
}

export const GET = proxyHandler;
export const POST = proxyHandler;
export const PUT = proxyHandler;
export const PATCH = proxyHandler;
export const DELETE = proxyHandler;
