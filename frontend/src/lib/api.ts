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
    // Get token from OIDC storage
    // react-oidc-context stores user in sessionStorage with key pattern:
    // oidc.user:<authority>:<client_id>
    const authority = import.meta.env.VITE_ZITADEL_AUTHORITY;
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
      // Token expired or invalid - clear OIDC storage and redirect
      const authority = import.meta.env.VITE_ZITADEL_AUTHORITY;
      const clientId = import.meta.env.VITE_ZITADEL_CLIENT_ID;
      const storageKey = `oidc.user:${authority}:${clientId}`;
      localStorage.removeItem(storageKey);
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

// Types

export interface DNO {
  id: string;
  slug: string;
  name: string;
  official_name?: string;
  vnb_id?: string;
  status?: "uncrawled" | "crawling" | "crawled" | "failed";
  crawl_locked_at?: string;
  description?: string;
  region?: string;
  website?: string;
  data_points_count?: number;
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
  verification_status?: string;
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
  year?: number;
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
  winter?: string;
  fruehling?: string;
  sommer?: string;
  herbst?: string;
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
  user_id?: string;
  year: number;
  data_type: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  current_step?: string;
  error_message?: string;
  priority: number;
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

export interface JobDetails extends Job {
  dno_slug?: string;
  updated_at?: string;
  steps: JobStep[];
}

// User info response from /auth/me endpoint
export interface UserInfo {
  id: string;
  email: string;
  name: string;
  roles: string[];
  is_admin: boolean;
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

  dnos: {
    async list(include_stats?: boolean): Promise<ApiResponse<DNO[]>> {
      const { data } = await apiClient.get("/dnos/", {
        params: { include_stats },
      });
      return data;
    },

    async get(dno_id: string): Promise<ApiResponse<DNO>> {
      const { data } = await apiClient.get(`/dnos/${dno_id}`);
      return data;
    },

    async triggerCrawl(
      dno_id: string,
      payload: { year: number; data_type?: string; priority?: number }
    ): Promise<ApiResponse<{ job_id: string }>> {
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
    }): Promise<ApiResponse<DNO>> {
      const { data } = await apiClient.post("/dnos/", payload);
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
  },

  admin: {
    async getDashboard(): Promise<
      ApiResponse<{
        dnos: { total: number };
        jobs: { pending: number; running: number };
      }>
    > {
      const { data } = await apiClient.get("/admin/dashboard");
      return data;
    },

    async listJobs(params?: {
      status?: string;
      page?: number;
      per_page?: number;
    }): Promise<ApiResponse<Job[]>> {
      const { data } = await apiClient.get("/admin/jobs", { params });
      return data;
    },

    async getJob(jobId: string): Promise<ApiResponse<JobDetails>> {
      const { data } = await apiClient.get(`/admin/jobs/${jobId}`);
      return data;
    },

    async createJob(payload: {
      dno_id: number;
      year: number;
      data_type?: string;
      priority?: number;
      job_type?: string;
      target_file_id?: number;
    }): Promise<ApiResponse<{ job_id: string }>> {
      const { data } = await apiClient.post("/admin/jobs", payload);
      return data;
    },

    async rerunJob(jobId: string): Promise<ApiResponse<{ job_id: string }>> {
      const { data } = await apiClient.post(`/admin/jobs/${jobId}/rerun`);
      return data;
    },

    async cancelJob(jobId: string): Promise<ApiResponse<null>> {
      const { data } = await apiClient.delete(`/admin/jobs/${jobId}`);
      return data;
    },
  },
};

export default api;
