/**
 * Shared utility functions for DNO detail page data handling
 */

/**
 * Check if a value contains "real" data (not null, "-", "N/A", or empty)
 */
export function isValidValue(v: unknown): boolean {
    if (v === null || v === undefined) return false;
    const str = String(v).trim().toLowerCase();
    return str !== "-" && str !== "n/a" && str !== "" && str !== "null";
}

/**
 * Format a date string for display
 */
export function formatDate(dateStr?: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });
}

/**
 * Format a date string with time for display
 */
export function formatDateTime(dateStr?: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

/**
 * Format a number with German locale (comma as decimal separator)
 */
export function formatNumber(value?: number | null, decimals = 2): string {
    if (value === null || value === undefined) return "-";
    return value.toLocaleString("de-DE", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

/**
 * Format bytes to human-readable size
 */
export function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Get status color classes for DNO/job status
 */
export function getStatusColor(status: string): { bg: string; text: string; border: string } {
    switch (status) {
        case "completed":
        case "crawled":
        case "verified":
            return {
                bg: "bg-green-50 dark:bg-green-900/20",
                text: "text-green-600 dark:text-green-400",
                border: "border-green-200 dark:border-green-800",
            };
        case "running":
        case "pending":
            return {
                bg: "bg-blue-50 dark:bg-blue-900/20",
                text: "text-blue-600 dark:text-blue-400",
                border: "border-blue-200 dark:border-blue-800",
            };
        case "failed":
        case "error":
            return {
                bg: "bg-red-50 dark:bg-red-900/20",
                text: "text-red-600 dark:text-red-400",
                border: "border-red-200 dark:border-red-800",
            };
        case "flagged":
            return {
                bg: "bg-amber-50 dark:bg-amber-900/20",
                text: "text-amber-600 dark:text-amber-400",
                border: "border-amber-200 dark:border-amber-800",
            };
        default:
            return {
                bg: "bg-gray-50 dark:bg-gray-900/20",
                text: "text-gray-600 dark:text-gray-400",
                border: "border-gray-200 dark:border-gray-700",
            };
    }
}

/**
 * Standard voltage level order for sorting
 */
export const VOLTAGE_LEVEL_ORDER = ["HöS", "HöS/HS", "HS", "HS/MS", "MS", "MS/NS", "NS"];

/**
 * Sort voltage levels in standard order
 */
export function sortByVoltageLevel<T extends { voltage_level: string }>(items: T[]): T[] {
    return [...items].sort((a, b) => {
        const indexA = VOLTAGE_LEVEL_ORDER.indexOf(a.voltage_level);
        const indexB = VOLTAGE_LEVEL_ORDER.indexOf(b.voltage_level);
        // Put unknown levels at the end
        const orderA = indexA === -1 ? 999 : indexA;
        const orderB = indexB === -1 ? 999 : indexB;
        return orderA - orderB;
    });
}
