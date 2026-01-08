/**
 * Status constants and helpers.
 */

import type { DNOStatus, JobStatus } from "@/types";

// DNO status display configuration
export const DNO_STATUS_CONFIG: Record<
    DNOStatus,
    { label: string; color: string; bgColor: string }
> = {
    uncrawled: {
        label: "Uncrawled",
        color: "text-gray-600",
        bgColor: "bg-gray-100",
    },
    pending: {
        label: "Pending",
        color: "text-yellow-600",
        bgColor: "bg-yellow-100",
    },
    running: {
        label: "Running",
        color: "text-blue-600",
        bgColor: "bg-blue-100",
    },
    crawled: {
        label: "Crawled",
        color: "text-green-600",
        bgColor: "bg-green-100",
    },
    failed: {
        label: "Failed",
        color: "text-red-600",
        bgColor: "bg-red-100",
    },
};

// Job status display configuration
export const JOB_STATUS_CONFIG: Record<
    JobStatus,
    { label: string; color: string; bgColor: string }
> = {
    pending: {
        label: "Pending",
        color: "text-yellow-600",
        bgColor: "bg-yellow-100",
    },
    running: {
        label: "Running",
        color: "text-blue-600",
        bgColor: "bg-blue-100",
    },
    completed: {
        label: "Completed",
        color: "text-green-600",
        bgColor: "bg-green-100",
    },
    failed: {
        label: "Failed",
        color: "text-red-600",
        bgColor: "bg-red-100",
    },
    cancelled: {
        label: "Cancelled",
        color: "text-gray-600",
        bgColor: "bg-gray-100",
    },
};

// Verification status configuration
export const VERIFICATION_STATUS_CONFIG = {
    verified: {
        label: "Verified",
        color: "text-green-600",
        bgColor: "bg-green-100",
    },
    unverified: {
        label: "Unverified",
        color: "text-gray-600",
        bgColor: "bg-gray-100",
    },
    flagged: {
        label: "Flagged",
        color: "text-red-600",
        bgColor: "bg-red-100",
    },
} as const;

export type VerificationStatus = keyof typeof VERIFICATION_STATUS_CONFIG;
