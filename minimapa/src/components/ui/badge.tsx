import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-bold tracking-wide",
  {
    variants: {
      variant: {
        gold: "bg-gold/12 text-gold-light ring-1 ring-gold/25",
        green: "bg-green/12 text-green ring-1 ring-green/25",
        red: "bg-red/12 text-red ring-1 ring-red/25",
        gray: "bg-white/[0.06] text-muted ring-1 ring-white/10",
      },
    },
    defaultVariants: { variant: "gray" },
  }
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

export function Badge({ className, variant, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            variant === "green" && "bg-green animate-glowPulse",
            variant === "red" && "bg-red",
            variant === "gold" && "bg-gold",
            (!variant || variant === "gray") && "bg-muted"
          )}
        />
      )}
      {children}
    </span>
  );
}
