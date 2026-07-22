import * as React from "react";
import { BrandMark } from "@/components/brand-mark";
import { SpaceCanvas } from "@/components/auth/space-canvas";

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <BrandMark className="size-6" />
      <span className="font-display text-lg font-semibold tracking-tight text-[#EDF1FA]">
        Vector Match
      </span>
    </span>
  );
}

interface AuthShellProps {
  eyebrow: string;
  title: string;
  description: string;
  footer: React.ReactNode;
  children: React.ReactNode;
}

export function AuthShell({
  eyebrow,
  title,
  description,
  footer,
  children,
}: AuthShellProps) {
  return (
    <div className="auth-dark relative flex min-h-dvh flex-1 flex-col overflow-hidden bg-[#070B14]">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_75%_60%_at_30%_20%,rgba(91,124,255,0.13),transparent_70%)]" />
      <div className="absolute inset-0 [background-image:radial-gradient(circle_at_center,rgba(123,144,255,0.09)_1px,transparent_1.5px)] [background-size:26px_26px]" />
      <SpaceCanvas className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_95%_85%_at_center,transparent_50%,rgba(7,11,20,0.6)_100%)]" />

      <header className="absolute left-5 top-5 z-10 md:left-8 md:top-8">
        <Wordmark />
      </header>

      <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-20 sm:px-6">
        <div className="w-full max-w-[400px] rounded-2xl border border-white/[0.08] bg-[#0B1120]/85 p-7 shadow-[0_32px_80px_-24px_rgba(0,0,0,0.7)] backdrop-blur-xl sm:p-9">
          <p className="font-mono text-[10px] tracking-[0.24em] text-[#5B7CFF]">
            {eyebrow}
          </p>
          <h1 className="mt-3 text-[26px] font-semibold tracking-tight text-[#EDF1FA]">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-[#8B95B0]">
            {description}
          </p>
          <div className="mt-8">{children}</div>
          {footer ? (
            <div className="mt-8 border-t border-white/[0.06] pt-5 text-center text-sm text-[#8B95B0]">
              {footer}
            </div>
          ) : null}
        </div>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 hidden items-end justify-between gap-4 p-5 sm:flex md:p-7">
        <div>
          <p className="font-mono text-[10px] tracking-[0.22em] text-[#7B90FF]/75">
            ℝ¹⁰²⁴ · COSINE · HNSW · TOP-3
          </p>
          <p className="mt-1.5 text-[13px] text-[#8B95B0]">
            让每段短文本，找到它的近邻。
          </p>
        </div>
        <p className="hidden shrink-0 font-mono text-[10px] tracking-[0.18em] text-[#46506B] md:block">
          FIG.01 — EMBEDDING SPACE
        </p>
      </div>
    </div>
  );
}

export const authFieldClass =
  "h-11 rounded-lg border-white/10 bg-white/[0.04] px-3.5 text-[15px] text-[#EAF0FB] placeholder:text-[#525D7C] focus-visible:border-[#5B7CFF]/70 focus-visible:ring-[#5B7CFF]/20 aria-invalid:border-[#FF8A66]/60 aria-invalid:ring-[#FF8A66]/15";

export const authLabelClass = "text-[13px] font-medium text-[#A7B0C8]";

export const authErrorClass =
  "rounded-lg border border-[#FF8A66]/25 bg-[#FF8A66]/[0.08] px-3.5 py-2.5 text-sm text-[#FFA585]";

export const authFieldErrorClass = "text-xs text-[#FF9E80]";

export const authSubmitClass =
  "mt-1 h-11 w-full rounded-lg bg-[#5B7CFF] text-sm font-medium text-white shadow-[0_8px_24px_-8px_rgba(91,124,255,0.55)] hover:bg-[#6E8CFF] focus-visible:border-[#8FA6FF] focus-visible:ring-[#5B7CFF]/30";

export const authLinkClass =
  "font-medium text-[#8FA6FF] underline-offset-4 transition-colors hover:text-[#B4C4FF] hover:underline";
