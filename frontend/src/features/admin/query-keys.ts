export const adminKeys = {
  all: ["admin"] as const,
  dashboard: ["admin", "dashboard"] as const,
  flagged: ["admin", "flagged"] as const,
  importance: {
    distribution: ["admin", "importance", "distribution"] as const,
  },
  cachedFiles: ["admin", "cached-files"] as const,
  bulkExtractStatus: ["admin", "bulk-extract-status"] as const,
  apiKeys: ["admin", "api-keys"] as const,
  ai: {
    config: ["admin", "ai-config"] as const,
    models: (providerType: string) => ["admin", "ai-models", providerType] as const,
  },
} as const;
