import { afterEach, describe, expect, it, vi } from "vitest";
import type { InternalAxiosRequestConfig } from "axios";

afterEach(() => { localStorage.clear(); vi.unstubAllEnvs(); vi.resetModules(); });

describe("Axios API contract", () => {
  it("keeps the search endpoint, JSON body and OIDC bearer header", async () => {
    vi.stubEnv("VITE_ZITADEL_AUTHORITY", "https://identity.invalid");
    vi.stubEnv("VITE_ZITADEL_CLIENT_ID", "test-client");
    localStorage.setItem("oidc.user:https://identity.invalid:test-client",
      JSON.stringify({ access_token: "synthetic-token" }));
    const { api, apiClient } = await import("./api");
    let captured: InternalAxiosRequestConfig | undefined;
    apiClient.defaults.adapter = async (config) => {
      captured = config;
      return { config, status: 200, statusText: "OK", headers: {},
        data: { found: false, has_data: false } };
    };
    const result = await api.publicSearch.search({ dno: { dno_name: "Test Netz" } });
    expect(captured?.url).toBe("/search/");
    expect(captured?.headers.get("Authorization")).toBe("Bearer synthetic-token");
    expect(captured?.headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(captured?.data)).toEqual({ dno: { dno_name: "Test Netz" } });
    expect(result).toEqual({ found: false, has_data: false });
  });
});
