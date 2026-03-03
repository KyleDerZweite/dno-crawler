/**
 * API key management types.
 */

export interface APIKeyInfo {
    id: number;
    name: string;
    key_prefix: string;
    roles: string[];
    is_active: boolean;
    request_count: number;
    last_used_at: string | null;
    created_at: string;
    created_by: string;
}

export interface APIKeyCreateRequest {
    name: string;
    roles: string[];
}

export interface APIKeyCreateResponse {
    id: number;
    name: string;
    key: string;
    key_prefix: string;
    roles: string[];
}
