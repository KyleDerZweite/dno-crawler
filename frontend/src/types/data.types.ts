/**
 * Data types for Netzentgelte and HLZF records.
 */

// Common extraction source types
export type ExtractionSource = "ai" | "html_parser" | "pdf_regex" | "manual" | null;
export type ExtractionFormat = "html" | "pdf" | null;

// Common verification fields
export interface VerificationFields {
    verification_status?: string;
    verified_by?: string;
    verified_at?: string;
    verification_notes?: string;
    flagged_by?: string;
    flagged_at?: string;
    flag_reason?: string;
}

// Common extraction tracking fields
export interface ExtractionFields {
    extraction_source?: ExtractionSource;
    extraction_model?: string | null;
    extraction_source_format?: ExtractionFormat;
    last_edited_by?: string | null;
    last_edited_at?: string | null;
}

// Netzentgelte (network charges) record
export interface Netzentgelte extends VerificationFields, ExtractionFields {
    id: number;
    type: "netzentgelte";
    dno_id: string;
    year: number;
    voltage_level: string;
    leistung?: number;
    arbeit?: number;
    leistung_unter_2500h?: number;
    arbeit_unter_2500h?: number;
}

// HLZF time range for parsed times
export interface HLZFTimeRange {
    start: string;  // e.g., "12:15:00"
    end: string;    // e.g., "13:15:00"
}

// HLZF (load time windows) record
export interface HLZF extends VerificationFields, ExtractionFields {
    id: number;
    type: "hlzf";
    dno_id: string;
    year: number;
    voltage_level: string;
    winter?: string | null;
    fruehling?: string | null;
    sommer?: string | null;
    herbst?: string | null;
    // Parsed time ranges
    winter_ranges?: HLZFTimeRange[];
    fruehling_ranges?: HLZFTimeRange[];
    sommer_ranges?: HLZFTimeRange[];
    herbst_ranges?: HLZFTimeRange[];
}

// Verification response from API
export interface VerificationResponse {
    id: number;
    verification_status: string;
    verified_by?: string;
    verified_at?: string;
    verification_notes?: string;
    flagged_by?: string;
    flagged_at?: string;
    flag_reason?: string;
    message: string;
}
