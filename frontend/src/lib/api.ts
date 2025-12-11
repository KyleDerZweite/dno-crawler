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

    const userJson = sessionStorage.getItem(storageKey);
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
      sessionStorage.removeItem(storageKey);
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
  description?: string;
  region?: string;
  website?: string;
  bundesland?: string;
  homepage_url?: string;
  netzentgelt_url?: string;
  is_active?: boolean;
  data_points_count?: number;
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

// Search Job types for natural language search with Timeline UI
export interface SearchFilters {
  years: number[];
  types: string[];
}

export interface SearchStep {
  step: number;
  label: string;
  status: "pending" | "running" | "done" | "failed";
  detail: string;
  started_at?: string;
  completed_at?: string;
}

export interface SearchJobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  current_step?: string;
  steps_history: SearchStep[];
  result?: {
    dno_name: string;
    netzentgelte: Record<number, unknown[]>;
    hlzf: Record<number, unknown[]>;
  };
  error?: string;
  created_at: string;
}

export interface SearchJobListItem {
  job_id: string;
  input_text: string;
  status: string;
  created_at: string;
  completed_at?: string;
}

// API functions
export const api = {
  auth: {
    // Get current user info from backend (validates token)
    async me(): Promise<ApiResponse<UserInfo>> {
      const { data } = await apiClient.get("/auth/me");
      return data;
    },
  },

  // Natural language search with Timeline UI
  search: {
    async create(
      prompt: string,
      filters?: SearchFilters
    ): Promise<{ job_id: string; status: string; message: string }> {
      const { data } = await apiClient.post("/search", {
        prompt,
        filters: filters || { years: [2024, 2025], types: ["netzentgelte", "hlzf"] },
      });
      return data;
    },

    async getStatus(jobId: string): Promise<SearchJobStatus> {
      const { data } = await apiClient.get(`/search/${jobId}/status`);
      return data;
    },

    async getJob(jobId: string): Promise<SearchJobStatus> {
      const { data } = await apiClient.get(`/search/${jobId}`);
      return data;
    },

    async getHistory(limit?: number): Promise<SearchJobListItem[]> {
      const { data } = await apiClient.get("/search/history", {
        params: { limit: limit || 20 },
      });
      return data;
    },
  },

  public: {
    async searchData(params: {
      dno?: string;
      year?: number;
      data_type?: "netzentgelte" | "hlzf" | "all";
      page?: number;
      per_page?: number;
    }): Promise<ApiResponse<(Netzentgelte | HLZF)[]>> {
      const { data } = await apiClient.get("/search", { params });
      return data;
    },

    async listDNOs(params?: {
      region?: string;
      page?: number;
      per_page?: number;
    }): Promise<ApiResponse<DNO[]>> {
      const { data } = await apiClient.get("/dnos", { params });
      return data;
    },

    async getDNO(slug: string): Promise<ApiResponse<DNO>> {
      const { data } = await apiClient.get(`/dnos/${slug}`);
      return data;
    },

    async getYears(dno_slug?: string): Promise<ApiResponse<number[]>> {
      const { data } = await apiClient.get("/years", {
        params: { dno_slug },
      });
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
