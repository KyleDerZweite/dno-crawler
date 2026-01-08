/**
 * API configuration constants.
 */

// API base URL
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// Pagination defaults
export const DEFAULT_PAGE_SIZE = 50;
export const PAGE_SIZE_OPTIONS = [25, 50, 100, 250] as const;

// Year range for data
export const MIN_YEAR = 2020;
export const MAX_YEAR = new Date().getFullYear() + 1;
export const DEFAULT_YEAR = new Date().getFullYear();

// Generate array of available years
export function getAvailableYears(
    startYear = MIN_YEAR,
    endYear = MAX_YEAR
): number[] {
    const years: number[] = [];
    for (let year = endYear; year >= startYear; year--) {
        years.push(year);
    }
    return years;
}

// Default data types
export const DATA_TYPES = ["all", "netzentgelte", "hlzf"] as const;
export type DataType = (typeof DATA_TYPES)[number];

// Job types
export const JOB_TYPES = ["full", "crawl", "extract"] as const;
