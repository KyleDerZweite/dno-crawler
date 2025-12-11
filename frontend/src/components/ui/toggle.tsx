import * as React from "react";
import { cn } from "@/lib/utils";

interface ToggleProps {
    pressed?: boolean;
    onPressedChange?: (pressed: boolean) => void;
    disabled?: boolean;
    size?: "default" | "sm" | "lg";
    variant?: "default" | "outline";
    className?: string;
    children?: React.ReactNode;
}

/**
 * Toggle - A simple toggle button component.
 * 
 * Similar to shadcn/ui Toggle but simplified.
 */
export function Toggle({
    pressed = false,
    onPressedChange,
    disabled = false,
    size = "default",
    variant = "default",
    className,
    children,
}: ToggleProps) {
    const handleClick = () => {
        if (!disabled && onPressedChange) {
            onPressedChange(!pressed);
        }
    };

    const sizeClasses = {
        default: "h-10 px-4",
        sm: "h-8 px-3 text-sm",
        lg: "h-12 px-6",
    };

    const variantClasses = pressed
        ? "bg-primary text-primary-foreground border-primary"
        : variant === "outline"
            ? "bg-transparent border-input hover:bg-accent/50"
            : "bg-muted";

    return (
        <button
            type="button"
            role="switch"
            aria-checked={pressed}
            disabled={disabled}
            onClick={handleClick}
            className={cn(
                "inline-flex items-center justify-center rounded-md border font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:pointer-events-none disabled:opacity-50",
                sizeClasses[size],
                variantClasses,
                className
            )}
        >
            {children}
        </button>
    );
}
