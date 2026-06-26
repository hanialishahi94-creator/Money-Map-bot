import * as React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[140px] w-full rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-text placeholder:text-muted/70 transition-all duration-300 resize-y",
          "focus:outline-none focus:border-gold/60 focus:bg-white/[0.05] focus:shadow-[0_0_0_3px_rgba(212,175,55,0.12)]",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";

export { Textarea };
