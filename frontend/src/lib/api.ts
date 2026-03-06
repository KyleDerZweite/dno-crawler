/**
 * API Client and Functions
 *
 * All type definitions live in @/types. Import types from there.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type {
  AIConfigCreate,
  AIConfigUpdate,
  AIProviderConfig,
  ApiResponse,
  APIKeyCreateRequest,
  APIKeyCreateResponse,
  APIKeyInfo,
  DNO,
  HLZF,
  Job,
  JobDetails,
  Netzentgelte,
  ProviderInfo,
  PublicSearchRequest,
  PublicSearchResponse,
  ReasoningOptions,
  ThinkingCapability,
  UserInfo,
  VNBDetails,
  VNBSuggestion,
  VerificationResponse,
} from "@/types";

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
// Guard to prevent infinite 401 redirect loops
let _isRedirecting = false;

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !_isRedirecting) {
      _isRedirecting = true;
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
      return data.data;
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
      status?: 'uncrawled' | 'crawled' | 'running' | 'pending' | 'protected';
      sort_by?: 'name_asc' | 'name_desc' | 'importance_asc' | 'importance_desc' | 'score_asc' | 'score_desc' | 'region_asc';
    }): Promise<ApiResponse<DNO[]>> {
      const { data } = await apiClient.get("/dnos/", {
        params: {
          include_stats: params?.include_stats,
          page: params?.page,
          per_page: params?.per_page,
          q: params?.q,
          status: params?.status,
          sort_by: params?.sort_by,
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
        priority?: number;
        job_type?: 'full' | 'extract';
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
        service_area_km2?: number;
        customer_count?: number;
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

    async getImportanceDistribution(): Promise<
      ApiResponse<{
        total: number;
        scored: number;
        p50: number;
        p90: number;
        histogram: { range: string; count: number }[];
        top: {
          id: number;
          slug: string;
          name: string;
          importance_score: number;
          importance_confidence: number | null;
          connection_points_count: number | null;
        }[];
        quality: {
          missing_score: number;
          fallback_customers: number;
          fallback_area: number;
        };
      }>
    > {
      const { data } = await apiClient.get("/admin/importance/distribution");
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

    // API Key Management
    async getAPIKeys(): Promise<{ keys: APIKeyInfo[] }> {
      const { data } = await apiClient.get("/api-keys");
      return data;
    },

    async createAPIKey(request: APIKeyCreateRequest): Promise<APIKeyCreateResponse> {
      const { data } = await apiClient.post("/api-keys", request);
      return data;
    },

    async deleteAPIKey(id: number): Promise<{ message: string }> {
      const { data } = await apiClient.delete(`/api-keys/${id}`);
      return data;
    },

    // AI Configuration - using new /ai/* endpoints
    async getAIConfigs(): Promise<
      ApiResponse<{
        configs: AIProviderConfig[];
        total: number;
      }>
    > {
      const { data } = await apiClient.get("/ai/configs");
      return data;
    },

    async createAIConfig(config: AIConfigCreate): Promise<
      ApiResponse<{ id: number }>
    > {
      const { data } = await apiClient.post("/ai/configs", config);
      return data;
    },

    async updateAIConfig(
      configId: number,
      config: AIConfigUpdate
    ): Promise<ApiResponse<null>> {
      const { data } = await apiClient.patch(
        `/ai/configs/${configId}`,
        config
      );
      return data;
    },

    async deleteAIConfig(configId: number): Promise<ApiResponse<null>> {
      const { data } = await apiClient.delete(`/ai/configs/${configId}`);
      return data;
    },

    async reorderAIConfigs(
      configIds: number[]
    ): Promise<ApiResponse<null>> {
      const { data } = await apiClient.post("/ai/configs/reorder", {
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
        `/ai/configs/${configId}/test`
      );
      return data;
    },

    async testAIConfigPreview(config: {
      provider_type: string;
      auth_type: string;
      model: string;
      api_key?: string;
      api_url?: string;
      model_parameters?: Record<string, unknown>;
    }): Promise<
      ApiResponse<{
        model: string;
        response?: string;
        elapsed_ms: number;
        error?: string;
      }>
    > {
      const { data } = await apiClient.post("/ai/configs/test", config);
      return data;
    },

    async getAIProviders(): Promise<
      ApiResponse<{
        providers: Record<string, ProviderInfo>;
      }>
    > {
      const { data } = await apiClient.get("/ai/providers");
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
        provider_type: string;
        provider_info?: ProviderInfo;
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
          cost_input?: number | null;
          cost_output?: number | null;
          cost_cache_read?: number | null;
          context_limit?: number | null;
          output_limit?: number | null;
          tier?: "high" | "efficient" | "budget" | "free";
          release_date?: string | null;
          knowledge_cutoff?: string | null;
          open_weights?: boolean;
          thinking_capability?: ThinkingCapability;
        }[];
        default_url: string | null;
        default_model?: string;
        reasoning_options?: ReasoningOptions | null;
      }>
    > {
      const { data } = await apiClient.get(
        `/ai/providers/${providerType}`,
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
      const { data } = await apiClient.get("/ai/status");
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
