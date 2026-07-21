import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

type LoginBackendResponse = {
  token: string;
  user: {
    id: string;
    username: string;
    email: string | null;
    isSuperuser: boolean;
  };
};

export async function POST(req: NextRequest) {
  let body: string;
  try {
    body = await req.text();
  } catch {
    return NextResponse.json({ detail: "invalid request body" }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body,
    });
  } catch {
    return NextResponse.json(
      { detail: "backend unavailable" },
      { status: 502 },
    );
  }

  const resBody = await backendRes.text();

  if (backendRes.status !== 200) {
    return new NextResponse(resBody, {
      status: backendRes.status,
      headers: {
        "Content-Type": backendRes.headers.get("content-type") ?? "application/json",
      },
    });
  }

  let parsed: LoginBackendResponse;
  try {
    parsed = JSON.parse(resBody);
  } catch {
    return NextResponse.json(
      { detail: "invalid backend response" },
      { status: 502 },
    );
  }

  if (!parsed.token || typeof parsed.token !== "string") {
    return NextResponse.json(
      { detail: "invalid backend response" },
      { status: 502 },
    );
  }

  const response = NextResponse.json(parsed.user);
  const maxAge = Number(process.env.SESSION_MAX_AGE ?? 604800);
  response.cookies.set({
    name: "session",
    value: parsed.token,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge,
    secure: process.env.NODE_ENV === "production",
  });
  return response;
}
