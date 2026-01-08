/**
 * Core DNO types and related entities.
 */

// Address components used across multiple entities
export interface AddressComponents {
    street?: string;
    house_number?: string;
    zip_code?: string;
    city?: string;
    country?: string;
}

// External source data types
export interface MastrData {
    mastr_nr: string;
    acer_code?: string;
    registered_name: string;
    region?: string;
    address_components?: AddressComponents;
    contact_address?: string;
    marktrollen?: string[];
    is_active?: boolean;
    closed_network?: boolean;
    activity_start?: string;
    activity_end?: string;
    registration_date?: string;
    mastr_last_updated?: string;
    last_synced_at?: string;
}

export interface VnbData {
    vnb_id: string;
    name: string;
    official_name?: string;
    homepage_url?: string;
    phone?: string;
    email?: string;
    address?: string;
    types?: string[];
    voltage_types?: string[];
    logo_url?: string;
    is_electricity?: boolean;
    last_synced_at?: string;
}

export interface BdewData {
    bdew_code: string;
    bdew_internal_id: number;
    bdew_company_uid: number;
    company_name: string;
    market_function?: string;
    contact_name?: string;
    contact_phone?: string;
    contact_email?: string;
    street?: string;
    zip_code?: string;
    city?: string;
    website?: string;
    is_grid_operator?: boolean;
    last_synced_at?: string;
}

// DNO status type
export type DNOStatus = "uncrawled" | "pending" | "running" | "crawled" | "failed";

// Main DNO entity
export interface DNO {
    id: string;
    slug: string;
    name: string;
    official_name?: string;
    vnb_id?: string;
    mastr_nr?: string;
    primary_bdew_code?: string;
    // Status tracking
    status?: DNOStatus;
    crawl_locked_at?: string;
    source?: "seed" | "user_discovery";
    // Basic info
    description?: string;
    region?: string;
    website?: string;
    // Computed display fields
    display_name?: string;
    display_website?: string;
    display_phone?: string;
    display_email?: string;
    // Legacy fields (for backward compat)
    phone?: string;
    email?: string;
    contact_address?: string;
    address_components?: AddressComponents;
    marktrollen?: string[];
    acer_code?: string;
    grid_operator_bdew_code?: string;
    // MaStR metadata (legacy)
    registration_date?: string;
    mastr_last_updated?: string;
    closed_network?: boolean;
    is_active?: boolean;
    // Crawlability info
    crawlable?: boolean;
    crawl_blocked_reason?: string;
    has_local_files?: boolean;
    // Source data availability
    has_mastr?: boolean;
    has_vnb?: boolean;
    has_bdew?: boolean;
    enrichment_sources?: string[];
    enrichment_status?: "pending" | "processing" | "completed" | "failed";
    last_enriched_at?: string;
    // Source data objects
    mastr_data?: MastrData;
    vnb_data?: VnbData;
    bdew_data?: BdewData[];
    // Stats
    data_points_count?: number;
    netzentgelte_count?: number;
    hlzf_count?: number;
    created_at?: string;
    updated_at?: string;
}

// VNB search types (for DNO autocomplete)
export interface VNBSuggestion {
    vnb_id: string;
    name: string;
    subtitle?: string;  // Official legal name (e.g., "GmbH")
    logo_url?: string;
    exists: boolean;    // Already in our database
    existing_dno_id?: string;
    existing_dno_slug?: string;
}

export interface VNBDetails {
    vnb_id: string;
    name: string;
    website?: string;
    phone?: string;
    email?: string;
    address?: string;
}
