/**
 * API Client and Functions
 * 
 * NOTE: Type definitions are now also available in @/types directory.
 * New code should prefer importing from '@/types' and '@/constants'.
 * Types in this file are kept for backwards compatibility.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor to add auth token from OIDC session
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Detect if auth is enabled based on authority URL
    const authority = import.meta.env.VITE_ZITADEL_AUTHORITY;
    const isAuthEnabled = authority && authority !== "https://auth.example.com";
    if (!isAuthEnabled) return config;

    const clientId = import.meta.env.VITE_ZITADEL_CLIENT_ID;
    const storageKey = `oidc.user:${authority}:${clientId}`;

    const userJson = localStorage.getItem(storageKey);
    if (userJson) {
      try {
        const user = JSON.parse(userJson);
        if (user.access_token) {
          config.headers.set("Authorization", `Bearer ${user.access_token}`);
        }
      } catch {
        // Invalid JSON, ignore
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear OIDC storage and force full reload
      const authority = import.meta.env.VITE_ZITADEL_AUTHORITY;
      const clientId = import.meta.env.VITE_ZITADEL_CLIENT_ID;
      const storageKey = `oidc.user:${authority}:${clientId}`;
      localStorage.removeItem(storageKey);
      // Force full page reload to reset OIDC in-memory state
      window.location.replace("/");
    }
    return Promise.reject(error);
  }
);

// Types

// AI Provider Configuration Types
export type AIProviderType = "openai" | "google" | "anthropic" | "openrouter" | "litellm" | "custom";
export type AIAuthType = "api_key" | "oauth" | "cli";

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
  has_oauth: boolean;
  supports_text: boolean;
  supports_vision: boolean;
  supports_files: boolean;
  is_enabled: boolean;
  priority: number;
  status: "active" | "disabled" | "rate_limited" | "unhealthy" | "untested";
  is_subscription: boolean;
  model_parameters: Record<string, any> | null;
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
  model_parameters?: Record<string, any>;
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
  model_parameters?: Record<string, any>;
}


export interface AddressComponents {
  street?: string;
  house_number?: string;
  zip_code?: string;
  city?: string;
  country?: string;
}

// Source Data Types
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

export interface DNO {
  id: string;
  slug: string;
  name: string;
  official_name?: string;
  vnb_id?: string;
  mastr_nr?: string;
  primary_bdew_code?: string;
  // Status tracking
  status?: "uncrawled" | "pending" | "running" | "crawled" | "failed";
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

export interface Netzentgelte {
  id: number;
  type: "netzentgelte";
  dno_id: string;
  year: number;
  voltage_level: string;
  leistung?: number;
  arbeit?: number;
  leistung_unter_2500h?: number;
  arbeit_unter_2500h?: number;
  verification_status?: string;
  verified_by?: string;
  verified_at?: string;
  verification_notes?: string;
  flagged_by?: string;
  flagged_at?: string;
  flag_reason?: string;
  // Extraction source tracking
  extraction_source?: "ai" | "html_parser" | "pdf_regex" | "manual" | null;
  extraction_model?: string | null;
  extraction_source_format?: "html" | "pdf" | null;
  last_edited_by?: string | null;
  last_edited_at?: string | null;
}

export interface HLZFTimeRange {
  start: string;  // e.g., "12:15:00"
  end: string;    // e.g., "13:15:00"
}

export interface HLZF {
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
  verification_status?: string;
  verified_by?: string;
  verified_at?: string;
  flagged_by?: string;
  flagged_at?: string;
  flag_reason?: string;
  // Extraction source tracking
  extraction_source?: "ai" | "html_parser" | "pdf_regex" | "manual" | null;
  extraction_model?: string | null;
  extraction_source_format?: "html" | "pdf" | null;
  last_edited_by?: string | null;
  last_edited_at?: string | null;
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

// =============================================================================
// Public Search Types (Decoupled Search API)
// =============================================================================

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

export interface PublicSearchDNO {
  id: number;
  slug: string;
  name: string;
  official_name?: string;
  vnb_id?: string;
  status: string;
}

export interface PublicSearchLocation {
  street: string;
  number?: string;
  zip_code: string;
  city: string;
  latitude: number;
  longitude: number;
}

export interface PublicSearchNetzentgelte {
  year: number;
  voltage_level: string;
  leistung?: number;
  arbeit?: number;
}

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

export interface PublicSearchResponse {
  found: boolean;
  has_data: boolean;
  dno?: PublicSearchDNO;
  location?: PublicSearchLocation;
  netzentgelte?: PublicSearchNetzentgelte[];
  hlzf?: PublicSearchHLZF[];
  message?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data: T;
  meta?: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

export interface Job {
  id: string;
  dno_id: string;
  dno_name?: string;
  year: number;
  data_type: string;
  job_type?: 'full' | 'crawl' | 'extract';
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  current_step?: string;
  error_message?: string;
  triggered_by?: string;
  priority: number;
  parent_job_id?: string;
  child_job_id?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface JobStep {
  id: string;
  step_name: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  details?: Record<string, unknown>;
}

export interface ExtractionLog {
  prompt: string;
  response: unknown;
  file_metadata: {
    path: string;
    name: string;
    format: string;
    size_bytes: number;
    pages?: number;
  };
  model?: string | null;
  mode: "vision" | "text" | "fallback";
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
}

export interface JobDetails extends Job {
  dno_slug?: string;
  updated_at?: string;
  steps: JobStep[];
  extraction_log?: ExtractionLog;
  parent_job?: {
    id: string;
    job_type: string;
    status: string;
  };
  child_job?: {
    id: string;
    job_type: string;
    status: string;
  };
}

// User info response from /auth/me endpoint
export interface UserInfo {
  id: string;
  email: string;
  name: string;
  roles: string[];
  is_admin: boolean;
}

// VNB Search Types (for DNO autocomplete)
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

// NOTE: Old batch/timeline types removed - now using PublicSearch types above

// API functions
export const api = {
  auth: {
    // Get current user info from backend (validates token)
    async me(): Promise<ApiResponse<UserInfo>> {
      const { data } = await apiClient.get("/auth/me");
      return data;
    },
  },

  // Public Search API (Decoupled - skeleton creation)
  publicSearch: {
    /**
     * Search for DNO by address, coordinates, or name.
     * Returns existing data or creates skeleton DNO.
     * Auth token sent for better rate limiting.
     */
    async search(request: PublicSearchRequest): Promise<PublicSearchResponse> {
      const { data } = await apiClient.post("/search/", request);
      return data;
    },
  },

  // Jobs API - Unified job management
  jobs: {
    async list(params?: {
      status?: string;
      limit?: number;
      page?: number;
    }): Promise<{
      jobs: {
        job_id: string;
        dno_id: string;
        dno_name?: string;
        year: number;
        data_type: string;
        status: string;
        progress: number;
        current_step?: string;
        error_message?: string;
        queue_position?: number;
        started_at?: string;
        completed_at?: string;
        created_at?: string;
      }[];
      queue_length: number;
      meta?: {
        total: number;
        page: number;
        per_page: number;
        total_pages: number;
      };
    }> {
      const { data } = await apiClient.get("/jobs/", { params });
      return data;
    },

    async get(jobId: string): Promise<ApiResponse<JobDetails>> {
      const { data } = await apiClient.get(`/jobs/${jobId}`);
      return data;
    },

    async delete(jobId: string): Promise<ApiResponse<{ job_id: string }>> {
      const { data } = await apiClient.delete(`/jobs/${jobId}`);
      return data;
    },
  },

  dnos: {
    async getStats(): Promise<ApiResponse<{
      total_dnos: number;
      netzentgelte_count: number;
      hlzf_count: number;
      total_data_points: number;
      active_crawls: number;
    }>> {
      const { data } = await apiClient.get("/dnos/stats");
      return data;
    },

    async list(params?: {
      include_stats?: boolean;
      page?: number;
      per_page?: number;
      q?: string;
    }): Promise<ApiResponse<DNO[]>> {
      const { data } = await apiClient.get("/dnos/", {
        params: {
          include_stats: params?.include_stats,
          page: params?.page,
          per_page: params?.per_page,
          q: params?.q,
        },
      });
      return data;
    },

    async get(dno_id: string): Promise<ApiResponse<DNO>> {
      const { data } = await apiClient.get(`/dnos/${dno_id}`);
      return data;
    },

    async triggerCrawl(
      dno_id: string,
      payload: {
        year: number;
        data_type?: 'all' | 'netzentgelte' | 'hlzf';
        priority?: number;
        job_type?: 'full' | 'crawl' | 'extract';
      }
    ): Promise<ApiResponse<{ job_id: string; job_type: string }>> {
      const { data } = await apiClient.post(`/dnos/${dno_id}/crawl`, payload);
      return data;
    },

    async create(payload: {
      name: string;
      slug?: string;
      official_name?: string;
      description?: string;
      region?: string;
      website?: string;
      vnb_id?: string;
      phone?: string;
      email?: string;
      contact_address?: string;
    }): Promise<ApiResponse<DNO>> {
      const { data } = await apiClient.post("/dnos/", payload);
      return data;
    },

    // VNB Digital search for autocomplete
    async searchVnb(query: string): Promise<ApiResponse<{ suggestions: VNBSuggestion[]; count: number }>> {
      const { data } = await apiClient.get("/dnos/search-vnb", {
        params: { q: query },
      });
      return data;
    },

    // Get extended VNB details for auto-fill
    async getVnbDetails(vnb_id: string): Promise<ApiResponse<VNBDetails>> {
      const { data } = await apiClient.get(`/dnos/search-vnb/${vnb_id}/details`);
      return data;
    },

    async updateDNO(
      dno_id: string,
      payload: {
        name?: string;
        official_name?: string;
        description?: string;
        region?: string;
        website?: string;
      }
    ): Promise<ApiResponse<{ id: string }>> {
      const { data } = await apiClient.patch(`/dnos/${dno_id}`, payload);
      return data;
    },

    async deleteDNO(dno_id: string): Promise<ApiResponse<{ id: string }>> {
      const { data } = await apiClient.delete(`/dnos/${dno_id}`);
      return data;
    },

    async getData(
      dno_id: string,
      params?: { year?: number; data_type?: string }
    ): Promise<ApiResponse<{
      dno: { id: string; name: string };
      netzentgelte: Netzentgelte[];
      hlzf: HLZF[];
    }>> {
      const { data } = await apiClient.get(`/dnos/${dno_id}/data`, { params });
      return data;
    },

    async getJobs(
      dno_id: string,
      limit?: number
    ): Promise<ApiResponse<Job[]>> {
      const { data } = await apiClient.get(`/dnos/${dno_id}/jobs`, {
        params: { limit: limit || 10 },
      });
      return data;
    },

    async updateNetzentgelte(
      dno_id: string,
      record_id: number,
      payload: {
        leistung?: number;
        arbeit?: number;
        leistung_unter_2500h?: number;
        arbeit_unter_2500h?: number;
      }
    ): Promise<ApiResponse<{ id: string }>> {
      const { data } = await apiClient.patch(
        `/dnos/${dno_id}/netzentgelte/${record_id}`,
        payload
      );
      return data;
    },

    async deleteNetzentgelte(
      dno_id: string,
      record_id: number
    ): Promise<ApiResponse<null>> {
      const { data } = await apiClient.delete(
        `/dnos/${dno_id}/netzentgelte/${record_id}`
      );
      return data;
    },

    async updateHLZF(
      dno_id: string,
      record_id: number,
      payload: {
        winter?: string;
        fruehling?: string;
        sommer?: string;
        herbst?: string;
      }
    ): Promise<ApiResponse<{ id: string }>> {
      const { data } = await apiClient.patch(
        `/dnos/${dno_id}/hlzf/${record_id}`,
        payload
      );
      return data;
    },

    async deleteHLZF(
      dno_id: string,
      record_id: number
    ): Promise<ApiResponse<null>> {
      const { data } = await apiClient.delete(
        `/dnos/${dno_id}/hlzf/${record_id}`
      );
      return data;
    },

    async getFiles(
      dno_id: string
    ): Promise<ApiResponse<{ name: string; size: number; path: string }[]>> {
      const { data } = await apiClient.get(`/dnos/${dno_id}/files`);
      return data;
    },

    async uploadFile(
      dno_id: string,
      file: File
    ): Promise<
      ApiResponse<{
        filename: string;
        path: string;
        detected_type: string | null;
        detected_year: number | null;
        original_filename: string;
        hint?: string;
      }>
    > {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post(`/dnos/${dno_id}/upload`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      return data;
    },

    // Export/Import endpoints
    async exportData(
      dno_id: string,
      params?: {
        data_types?: string[];
        years?: number[];
        include_metadata?: boolean;
      }
    ): Promise<Blob> {
      const response = await apiClient.get(`/dnos/${dno_id}/export`, {
        params: {
          data_types: params?.data_types,
          years: params?.years,
          include_metadata: params?.include_metadata ?? true,
        },
        responseType: "blob",
      });
      return response.data;
    },

    async importData(
      dno_id: string,
      payload: {
        mode: "merge" | "replace";
        netzentgelte?: {
          year: number;
          voltage_level: string;
          leistung?: number;
          arbeit?: number;
          leistung_unter_2500h?: number;
          arbeit_unter_2500h?: number;
          verification_status?: string;
          extraction_source?: string;
        }[];
        hlzf?: {
          year: number;
          voltage_level: string;
          winter?: string;
          fruehling?: string;
          sommer?: string;
          herbst?: string;
          verification_status?: string;
          extraction_source?: string;
        }[];
      }
    ): Promise<
      ApiResponse<{
        netzentgelte: { created: number; updated: number };
        hlzf: { created: number; updated: number };
        mode: string;
      }>
    > {
      const { data } = await apiClient.post(`/dnos/${dno_id}/import`, payload);
      return data;
    },
  },

  admin: {
    async getDashboard(): Promise<
      ApiResponse<{
        dnos: { total: number; uncrawled: number; crawled: number };
        jobs: { pending: number; running: number };
        data_points: { netzentgelte: number; hlzf: number; total: number };
        flagged: { netzentgelte: number; hlzf: number; total: number };
      }>
    > {
      const { data } = await apiClient.get("/admin/dashboard");
      return data;
    },

    async getFlagged(): Promise<
      ApiResponse<{
        items: {
          id: number;
          type: "netzentgelte" | "hlzf";
          year: number;
          voltage_level: string;
          flag_reason: string | null;
          flagged_at: string | null;
          flagged_by: string | null;
          dno_id: number;
          dno_name: string;
          dno_slug: string;
        }[];
        total: number;
      }>
    > {
      const { data } = await apiClient.get("/admin/flagged");
      return data;
    },

    // Cached files and bulk extraction
    async getCachedFiles(): Promise<
      ApiResponse<{
        total_files: number;
        files: {
          name: string;
          path: string;
          dno_slug: string;
          dno_id: number;
          dno_name: string;
          data_type: string;
          year: number;
          format: string;
          size: number;
          extraction_status: "no_data" | "flagged" | "verified" | "unverified";
        }[];
        by_data_type: { netzentgelte: number; hlzf: number };
        by_format: Record<string, number>;
        by_status: {
          no_data: number;
          flagged: number;
          verified: number;
          unverified: number;
        };
      }>
    > {
      const { data } = await apiClient.get("/admin/files");
      return data;
    },

    async previewBulkExtract(options: {
      mode: "flagged_only" | "default" | "force_override" | "no_data_and_failed";
      data_types?: string[];
      years?: number[];
      formats?: string[];
      dno_ids?: number[];
    }): Promise<
      ApiResponse<{
        total_files: number;
        will_extract: number;
        protected_verified: number;
        will_override_verified: number;
        flagged: number;
        no_data: number;
        unverified: number;
        failed_jobs: number;
        files: {
          name: string;
          path: string;
          dno_slug: string;
          dno_id: number;
          dno_name: string;
          data_type: string;
          year: number;
          format: string;
          will_extract: boolean;
          has_verified: boolean;
          has_flagged: boolean;
          has_data: boolean;
          has_failed_job?: boolean;
        }[];
      }>
    > {
      const { data } = await apiClient.post("/admin/extract/preview", options);
      return data;
    },

    async triggerBulkExtract(options: {
      mode: "flagged_only" | "default" | "force_override" | "no_data_and_failed";
      data_types?: string[];
      years?: number[];
      formats?: string[];
      dno_ids?: number[];
    }): Promise<
      ApiResponse<{
        jobs_queued: number;
        files_scanned: number;
      }>
    > {
      const { data } = await apiClient.post("/admin/extract/bulk", options);
      return data;
    },

    async getBulkExtractStatus(): Promise<
      ApiResponse<{
        total: number;
        pending: number;
        running: number;
        completed: number;
        failed: number;
        progress_percent: number;
      }>
    > {
      const { data } = await apiClient.get("/admin/extract/bulk/status");
      return data;
    },

    async cancelBulkExtract(): Promise<
      ApiResponse<{
        cancelled: number;
      }>
    > {
      const { data } = await apiClient.post("/admin/extract/bulk/cancel");
      return data;
    },

    async resetBulkExtract(): Promise<
      ApiResponse<{
        deleted: number;
      }>
    > {
      const { data } = await apiClient.delete("/admin/extract/bulk");
      return data;
    },

    // AI Configuration
    async getAIConfigs(): Promise<
      ApiResponse<{
        configs: AIProviderConfig[];
        total: number;
      }>
    > {
      const { data } = await apiClient.get("/admin/ai-config");
      return data;
    },

    async createAIConfig(config: AIConfigCreate): Promise<
      ApiResponse<{ id: number }>
    > {
      const { data } = await apiClient.post("/admin/ai-config", config);
      return data;
    },

    async updateAIConfig(
      configId: number,
      config: AIConfigUpdate
    ): Promise<ApiResponse<null>> {
      const { data } = await apiClient.patch(
        `/admin/ai-config/${configId}`,
        config
      );
      return data;
    },

    async deleteAIConfig(configId: number): Promise<ApiResponse<null>> {
      const { data } = await apiClient.delete(`/admin/ai-config/${configId}`);
      return data;
    },

    async reorderAIConfigs(
      configIds: number[]
    ): Promise<ApiResponse<null>> {
      const { data } = await apiClient.post("/admin/ai-config/reorder", {
        config_ids: configIds,
      });
      return data;
    },

    async testAIConfig(
      configId: number
    ): Promise<
      ApiResponse<{
        success: boolean;
        provider: string;
        model: string;
        message?: string;
        error?: string;
      }>
    > {
      const { data } = await apiClient.post(
        `/admin/ai-config/${configId}/test`
      );
      return data;
    },

    async testAIConfigPreview(config: {
      provider_type: string;
      auth_type: string;
      model: string;
      api_key?: string;
      api_url?: string;
    }): Promise<
      ApiResponse<{
        model: string;
        response?: string;
        elapsed_ms: number;
        error?: string;
      }>
    > {
      const { data } = await apiClient.post("/admin/ai-config/test", config);
      return data;
    },

    async getAIModels(
      providerType: string,
      options?: {
        query?: string;
        supports_vision?: boolean;
        supports_files?: boolean;
        limit?: number;
      }
    ): Promise<
      ApiResponse<{
        provider: string;
        models: {
          id: string;
          name: string;
          provider?: string;
          provider_name?: string;
          family?: string;
          supports_vision: boolean;
          supports_files: boolean;
          supports_audio?: boolean;
          supports_video?: boolean;
          reasoning?: boolean;
          tool_call?: boolean;
          // Pricing (per million tokens)
          cost_input?: number | null;
          cost_output?: number | null;
          cost_cache_read?: number | null;
          // Limits
          context_limit?: number | null;
          output_limit?: number | null;
          // Metadata
          tier?: "high" | "efficient" | "budget" | "free";
          release_date?: string | null;
          knowledge_cutoff?: string | null;
          open_weights?: boolean;
          thinking_capability?: ThinkingCapability;
        }[];
        default_url: string | null;
        custom_model_supported: boolean;
        source?: "suggested" | "search";
        query?: string;
        registry_status?: {
          loaded: boolean;
          loaded_at: string | null;
          providers: number;
          cache_file_exists: boolean;
        };
      }>
    > {
      const { data } = await apiClient.get(
        `/admin/ai-config/models/${providerType}`,
        {
          params: {
            query: options?.query,
            supports_vision: options?.supports_vision,
            supports_files: options?.supports_files,
            limit: options?.limit,
          },
        }
      );
      return data;
    },

    async refreshModelsRegistry(): Promise<ApiResponse<null>> {
      const { data } = await apiClient.post("/admin/ai-config/models/refresh");
      return data;
    },

    async getAIStatus(): Promise<
      ApiResponse<{
        ai_enabled: boolean;
        total_configs: number;
        enabled_configs: number;
        active_provider: {
          id: number;
          name: string;
          provider_type: string;
          model: string;
        } | null;
      }>
    > {
      const { data } = await apiClient.get("/admin/ai-config/status");
      return data;
    },

    // OAuth credential detection
    async detectCredentials(): Promise<
      ApiResponse<{
        credentials: {
          [key: string]: {
            available: boolean;
            source?: string | null;
            email?: string | null;
            name?: string | null;
            has_refresh_token?: boolean;
            instructions?: string;
            error?: string;
          };
        };
        any_available: boolean;
      }>
    > {
      const { data } = await apiClient.get("/admin/oauth/detect-credentials");
      return data;
    },

    async getGoogleOAuthStatus(): Promise<
      ApiResponse<{
        authenticated: boolean;
        user: { email: string | null; name: string | null } | null;
        gemini_cli_available: boolean;
        gemini_cli_email: string | null;
      }>
    > {
      const { data } = await apiClient.get("/admin/oauth/google/status");
      return data;
    },

    async useGeminiCliCredentials(): Promise<
      ApiResponse<{ email: string | null }>
    > {
      const { data } = await apiClient.post(
        "/admin/oauth/google/use-gemini-cli"
      );
      return data;
    },

    async startGoogleOAuth(redirectUri?: string): Promise<
      ApiResponse<{
        auth_url: string;
        state: string;
      }>
    > {
      const { data } = await apiClient.post("/admin/oauth/google/start", {
        redirect_uri: redirectUri,
      });
      return data;
    },

    async completeGoogleOAuth(code: string, state: string): Promise<
      ApiResponse<{
        email: string | null;
        name: string | null;
        expires_at: string | null;
      }>
    > {
      const { data } = await apiClient.post("/admin/oauth/google/callback", {
        code,
        state,
      });
      return data;
    },

    async logoutGoogleOAuth(): Promise<ApiResponse<null>> {
      const { data } = await apiClient.post("/admin/oauth/google/logout");
      return data;
    },
  },

  // Verification API - Data quality management
  verification: {
    // Netzentgelte verification
    async verifyNetzentgelte(
      recordId: number,
      notes?: string
    ): Promise<VerificationResponse> {
      const { data } = await apiClient.post(
        `/verification/netzentgelte/${recordId}/verify`,
        notes ? { notes } : undefined
      );
      return data;
    },

    async flagNetzentgelte(
      recordId: number,
      reason: string
    ): Promise<VerificationResponse> {
      const { data } = await apiClient.post(
        `/verification/netzentgelte/${recordId}/flag`,
        { reason }
      );
      return data;
    },

    async unflagNetzentgelte(recordId: number): Promise<VerificationResponse> {
      const { data } = await apiClient.delete(
        `/verification/netzentgelte/${recordId}/flag`
      );
      return data;
    },

    // HLZF verification
    async verifyHLZF(
      recordId: number,
      notes?: string
    ): Promise<VerificationResponse> {
      const { data } = await apiClient.post(
        `/verification/hlzf/${recordId}/verify`,
        notes ? { notes } : undefined
      );
      return data;
    },

    async flagHLZF(
      recordId: number,
      reason: string
    ): Promise<VerificationResponse> {
      const { data } = await apiClient.post(
        `/verification/hlzf/${recordId}/flag`,
        { reason }
      );
      return data;
    },

    async unflagHLZF(recordId: number): Promise<VerificationResponse> {
      const { data } = await apiClient.delete(
        `/verification/hlzf/${recordId}/flag`
      );
      return data;
    },
  },
};

export default api;
