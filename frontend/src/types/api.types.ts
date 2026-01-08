/**
 * Common API types.
 */

// Generic API response wrapper
export interface ApiResponse<T> {
    success: boolean;
    message?: string;
    data: T;
    meta?: PaginationMeta;
}

// Pagination metadata
export interface PaginationMeta {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
}

// User info from auth endpoint
export interface UserInfo {
    id: string;
    email: string;
    name: string;
    roles: string[];
    is_admin: boolean;
}
