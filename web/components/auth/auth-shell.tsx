import * as React from "react";
import { BrandMark } from "@/components/brand-mark";

const authEnterCss = `
@keyframes auth-enter {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.auth-enter {
  animation: auth-enter 600ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
@media (prefers-reduced-motion: reduce) {
  .auth-enter { animation: none; }
}
`;

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <BrandMark className="size-5" />
      <span className="font-mono text-[11px] font-medium uppercase tracking-[0.28em] text-[#171512]">
        Vector Match
      </span>
    </span>
  );
}

const FLOW_STEPS = [
  { index: "01", term: "PUSH", text: "批量推送短文本语料" },
  { index: "02", term: "TRAIN", text: "异步训练向量索引" },
  { index: "03", term: "SEARCH", text: "语义 / 全文 / 混合检索" },
] as const;

function EditorialIntro() {
  return (
    <div className="max-w-xl">
      <p className="flex items-center gap-2.5 font-mono text-[10px] uppercase tracking-[0.26em] text-[#8A8578]">
        <span className="inline-block size-2 bg-[#D9552C]" aria-hidden />
        Short-text retrieval console
      </p>
      <h1 className="mt-7 font-display text-[clamp(2.6rem,5.2vw,4.25rem)] leading-[1.05] font-semibold tracking-[-0.03em] text-[#141310]">
        信息很多<span className="text-[#D9552C]">,</span>
        <br />
        对的那条很少。
      </h1>
      <p className="mt-6 max-w-md text-[15px] leading-relaxed text-[#6F6A5E]">
        Vector Match 为短文本提供语义、全文与混合检索：推送语料，训练索引，
        把最相近的几条找回来。
      </p>

      <div className="mt-10 hidden max-w-md -rotate-[1.2deg] rounded-xl border border-[#E8E5DE] bg-white px-6 py-2 shadow-[0_24px_60px_-32px_rgba(23,21,18,0.045)] lg:block">
        {FLOW_STEPS.map((step, i) => (
          <div
            key={step.index}
            className={
              "flex items-baseline gap-4 py-3.5" +
              (i > 0 ? " border-t border-[#EFECE5]" : "")
            }
          >
            <span className="font-mono text-[10px] tracking-[0.2em] text-[#B8B2A4]">
              {step.index}
            </span>
            <span className="w-16 shrink-0 font-mono text-[11px] font-medium tracking-[0.18em] text-[#141310]">
              {step.term}
            </span>
            <span className="text-[13px] text-[#6F6A5E]">{step.text}</span>
          </div>
        ))}
      </div>
    </div>
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
    <div className="auth-light relative flex min-h-dvh flex-1 flex-col bg-[#F5F2EC] text-[#171512]">
      <style>{authEnterCss}</style>

      <header className="flex items-center justify-between border-b border-[#141310]/[0.07] px-5 py-4 md:px-10 md:py-5">
        <Wordmark />
        <p className="hidden font-mono text-[10px] uppercase tracking-[0.24em] text-[#8A8578] sm:block">
          Auth — Console
        </p>
      </header>

      <main className="flex flex-1 items-center px-5 py-12 md:px-10 md:py-16">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <section className="auth-enter">
            <EditorialIntro />
          </section>

          <section className="auth-enter flex [animation-delay:120ms] lg:justify-end">
            <div className="w-full max-w-[420px] rounded-xl border border-[#E8E5DE] bg-white p-7 shadow-[0_24px_60px_-28px_rgba(23,21,18,0.045)] sm:p-9">
              <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-[#B4542E]">
                {eyebrow}
              </p>
              <h2 className="mt-3 font-display text-[28px] font-semibold tracking-[-0.02em] text-[#141310]">
                {title}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-[#6F6A5E]">
                {description}
              </p>
              <div className="mt-8">{children}</div>
              {footer ? (
                <div className="mt-8 border-t border-[#EFECE5] pt-5 text-center text-sm text-[#6F6A5E]">
                  {footer}
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </main>

      <footer className="flex items-center justify-between border-t border-[#141310]/[0.07] px-5 py-4 md:px-10">
        <p className="font-mono text-[10px] tracking-[0.22em] text-[#8A8578]">
          ℝ¹⁰²⁴ · COSINE · HNSW · TOP-3
        </p>
        <p className="hidden shrink-0 font-mono text-[10px] uppercase tracking-[0.18em] text-[#B8B2A4] md:block">
          Fig.01 — Embedding space
        </p>
      </footer>
    </div>
  );
}

export const authFieldClass =
  "h-11 rounded-md border-[#E5E2DA] bg-white px-3.5 text-[15px] text-[#171512] placeholder:text-[#A9A294] focus-visible:border-[#141310]/50 focus-visible:ring-[#141310]/10 aria-invalid:border-[#D98A85] aria-invalid:ring-[#9F2F2D]/10";

export const authLabelClass = "text-[13px] font-medium text-[#57534A]";

export const authErrorClass =
  "rounded-md border border-[#F1D3D2] bg-[#FDEBEC] px-3.5 py-2.5 text-sm text-[#9F2F2D]";

export const authFieldErrorClass = "text-xs text-[#9F2F2D]";

export const authSubmitClass =
  "mt-1 h-11 w-full rounded-md bg-[#141310] text-sm font-medium text-[#FAF9F6] hover:bg-[#2E2C28] active:scale-[0.98] focus-visible:border-[#141310] focus-visible:ring-[#141310]/20";

export const authLinkClass =
  "font-medium text-[#141310] underline decoration-[#D9552C]/50 underline-offset-4 transition-colors hover:decoration-[#D9552C]";
