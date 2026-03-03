/**
 * AI provider configuration types.
 */

// Provider types are dynamically fetched, but we keep string type for compatibility
export type AIProviderType = string;
export type AIAuthType = "api_key";

// Provider info returned from backend (for dynamic UI)
export interface ProviderInfo {
    name: string;
    description: string;
    color: string;
    icon_svg: string;
    icon_emoji?: string;
}

// Reasoning options returned from backend (provider-specific)
export interface ReasoningOptions {
    method: "level" | "budget" | "both";
    levels?: string[];
    default_level?: string;
    budget_min?: number;
    budget_max?: number;
    default_budget?: number;
    param_name_effort?: string;
    param_name_tokens?: string;
}

export interface ThinkingCapability {
    method: "level" | "budget";
    options?: string[]; // For level: ["low", "medium", "high"]
    min?: number;      // For budget
    max?: number;      // For budget
    default?: string | number;
    can_disable?: boolean;
}

export interface AIProviderConfig {
    id: number;
    name: string;
    provider_type: AIProviderType;
    auth_type: AIAuthType;
    model: string;
    api_url: string | null;
    has_api_key: boolean;
    supports_text: boolean;
    supports_vision: boolean;
    supports_files: boolean;
    is_enabled: boolean;
    priority: number;
    status: "active" | "disabled" | "rate_limited" | "unhealthy" | "untested";
    model_parameters: Record<string, unknown> | null;
    last_success_at: string | null;
    last_error_at: string | null;
    last_error_message: string | null;
    consecutive_failures: number;
    total_requests: number;
    total_tokens_used: number;
    created_at: string | null;
}

export interface AIConfigCreate {
    name: string;
    provider_type: AIProviderType;
    auth_type?: AIAuthType;
    model: string;
    api_key?: string;
    api_url?: string;
    supports_text?: boolean;
    supports_vision?: boolean;
    supports_files?: boolean;
    model_parameters?: Record<string, unknown>;
}

export interface AIConfigUpdate {
    name?: string;
    model?: string;
    api_key?: string;
    api_url?: string;
    supports_text?: boolean;
    supports_vision?: boolean;
    supports_files?: boolean;
    is_enabled?: boolean;
    model_parameters?: Record<string, unknown>;
}
