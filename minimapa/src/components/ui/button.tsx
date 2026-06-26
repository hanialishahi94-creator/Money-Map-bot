import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-sm font-semibold transition-all duration-300 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-l from-gold-dark to-gold text-black shadow-gold hover:shadow-gold-lg hover:-translate-y-0.5",
        ghost:
          "border border-gold-dark/40 text-gold-light bg-transparent hover:bg-gold/10 hover:border-gold",
        outline:
          "border border-white/10 text-text bg-white/[0.02] hover:bg-white/[0.06] hover:border-white/20",
        danger:
          "bg-gradient-to-l from-red-700 to-red text-white shadow-[0_8px_24px_rgba(229,86,79,0.25)] hover:-translate-y-0.5",
        link: "text-gold-light underline-offset-4 hover:underline",
      },
      size: {
        default: "h-11 px-6",
        sm: "h-9 px-4 text-xs rounded-xl",
        lg: "h-12 px-8 text-base",
        icon: "h-10 w-10 rounded-xl",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
