import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("size-5", className)}
    >
      <line
        x1="8.9"
        y1="15.1"
        x2="16.3"
        y2="8.3"
        stroke="#FF6F4D"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="8" cy="16" r="2.6" fill="#FF6F4D" />
      <circle cx="17.4" cy="7.4" r="2.1" fill="#5B7CFF" />
      <circle cx="17" cy="17" r="1.4" fill="#5B7CFF" opacity="0.45" />
    </svg>
  );
}
