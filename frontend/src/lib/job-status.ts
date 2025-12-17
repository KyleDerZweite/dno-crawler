import { Clock, Loader2, CheckCircle, AlertCircle, Ban } from "lucide-react";

/**
 * Centralized job status configuration for consistent styling across the app.
 */
export const JOB_STATUS_CONFIG = {
    pending: { icon: Clock, color: "bg-yellow-500/10 text-yellow-500", label: "Pending" },
    running: { icon: Loader2, color: "bg-blue-500/10 text-blue-500", label: "Running" },
    completed: { icon: CheckCircle, color: "bg-green-500/10 text-green-500", label: "Completed" },
    failed: { icon: AlertCircle, color: "bg-red-500/10 text-red-500", label: "Failed" },
    cancelled: { icon: Ban, color: "bg-gray-500/10 text-gray-500", label: "Cancelled" },
} as const;

export type JobStatus = keyof typeof JOB_STATUS_CONFIG;
