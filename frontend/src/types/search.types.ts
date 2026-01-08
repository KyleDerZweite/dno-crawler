/**
 * Public search API types.
 */

import type { HLZFTimeRange } from "./data.types";

// Search request payload
export interface PublicSearchRequest {
    address?: {
        street: string;
        zip_code: string;
        city: string;
    };
    coordinates?: {
        latitude: number;
        longitude: number;
    };
    dno?: {
        dno_id?: string;
        dno_name?: string;
    };
    year?: number;           // Single year (backward compatible)
    years?: number[];        // Multiple years filter
}

// Simplified DNO in search results
export interface PublicSearchDNO {
    id: number;
    slug: string;
    name: string;
    official_name?: string;
    vnb_id?: string;
    status: string;
}

// Location in search results
export interface PublicSearchLocation {
    street: string;
    number?: string;
    zip_code: string;
    city: string;
    latitude: number;
    longitude: number;
}

// Netzentgelte in search results (simplified)
export interface PublicSearchNetzentgelte {
    year: number;
    voltage_level: string;
    leistung?: number;
    arbeit?: number;
}

// HLZF in search results (simplified)
export interface PublicSearchHLZF {
    year: number;
    voltage_level: string;
    // Raw string values (for display fallback)
    winter?: string;
    fruehling?: string;
    sommer?: string;
    herbst?: string;
    // Parsed time ranges (for structured display)
    winter_ranges?: HLZFTimeRange[];
    fruehling_ranges?: HLZFTimeRange[];
    sommer_ranges?: HLZFTimeRange[];
    herbst_ranges?: HLZFTimeRange[];
}

// Full search response
export interface PublicSearchResponse {
    found: boolean;
    has_data: boolean;
    dno?: PublicSearchDNO;
    location?: PublicSearchLocation;
    netzentgelte?: PublicSearchNetzentgelte[];
    hlzf?: PublicSearchHLZF[];
    message?: string;
}
