import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

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
      jobs: Array<{
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
      }>;
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
        items: Array<{
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
        }>;
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
        files: Array<{
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
        }>;
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
      mode: "flagged_only" | "default" | "force_override";
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
        files: Array<{
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
        }>;
      }>
    > {
      const { data } = await apiClient.post("/admin/extract/preview", options);
      return data;
    },

    async triggerBulkExtract(options: {
      mode: "flagged_only" | "default" | "force_override";
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
