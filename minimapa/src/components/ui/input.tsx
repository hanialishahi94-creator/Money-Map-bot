import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-11 w-full rounded-2xl border border-white/10 bg-white/[0.03] px-4 text-sm text-text placeholder:text-muted/70 transition-all duration-300",
        "focus:outline-none focus:border-gold/60 focus:bg-white/[0.05] focus:shadow-[0_0_0_3px_rgba(212,175,55,0.12)]",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
