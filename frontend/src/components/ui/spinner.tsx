import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SpinnerProps {
    className?: string;
    size?: "sm" | "md" | "lg";
    label?: string;
}

const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-6 w-6",
    lg: "h-8 w-8",
};

export function Spinner({ className, size = "md", label = "Loading" }: SpinnerProps) {
    return (
        <div className="inline-flex items-center" role="status" aria-busy="true">
            <Loader2 className={cn("animate-spin", sizeClasses[size], className)} />
            <span className="sr-only">{label}</span>
        </div>
    );
}

interface FullPageSpinnerProps {
    label?: string;
}

export function FullPageSpinner({ label = "Loading..." }: FullPageSpinnerProps) {
    return (
        <div className="flex h-screen items-center justify-center" role="status" aria-busy="true">
            <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4" />
                <span className="sr-only">{label}</span>
                <div className="text-lg">{label}</div>
            </div>
        </div>
    );
}