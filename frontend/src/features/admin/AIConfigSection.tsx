import { useState, useRef, useEffect, useMemo } from "react";
import { useToast } from "@/hooks/use-toast";
import { useErrorToast } from "@/hooks/use-error-toast";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AIProviderConfig, AIProviderType, AIConfigCreate } from "@/lib/api";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
    Brain,
    Plus,
    GripVertical,
    Trash2,
    RefreshCw,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Clock,
    Loader2,
    FileText,
    Image,
    File,
    Star,
    Key,
    ChevronDown,
    Check,
    Zap,
} from "lucide-react";

// Provider display info with logos from models.dev
const PROVIDER_INFO: Record<AIProviderType, { name: string; color: string; logoUrl: string }> = {
    openai: { name: "OpenAI", color: "bg-green-500/20 text-green-500", logoUrl: "https://models.dev/logos/openai.svg" },
    google: { name: "Google AI", color: "bg-blue-500/20 text-blue-500", logoUrl: "https://models.dev/logos/google.svg" },
    anthropic: { name: "Anthropic", color: "bg-orange-500/20 text-orange-500", logoUrl: "https://models.dev/logos/anthropic.svg" },
    openrouter: { name: "OpenRouter", color: "bg-purple-500/20 text-purple-500", logoUrl: "https://models.dev/logos/openrouter.svg" },
    litellm: { name: "LiteLLM", color: "bg-cyan-500/20 text-cyan-500", logoUrl: "https://models.dev/logos/litellm.svg" },
    custom: { name: "Custom", color: "bg-gray-500/20 text-gray-400", logoUrl: "" },
};

// Provider logo component
function ProviderLogo({ provider, className = "h-4 w-4" }: { provider: AIProviderType; className?: string }) {
    const info = PROVIDER_INFO[provider];
    if (!info.logoUrl) {
        return <span className={className}>🔧</span>;
    }
    return (
        <img
            src={info.logoUrl}
            alt={info.name}
            className={className}
            style={{
                // Invert dark logos to be light/white for dark theme visibility
                filter: 'brightness(0) invert(1) opacity(0.9)'
            }}
            onError={(e) => {
                // Fallback to a simple icon on error
                e.currentTarget.style.display = 'none';
            }}
        />
    );
}

// Status icons
const STATUS_ICONS: Record<string, React.ReactNode> = {
    active: <CheckCircle2 className="h-4 w-4 text-green-500" />,
    disabled: <XCircle className="h-4 w-4 text-muted-foreground" />,
    rate_limited: <Clock className="h-4 w-4 text-amber-500" />,
    unhealthy: <AlertTriangle className="h-4 w-4 text-red-500" />,
    untested: <RefreshCw className="h-4 w-4 text-muted-foreground" />,
};

// Provider options for the dropdown
const PROVIDER_OPTIONS: { value: AIProviderType; label: string }[] = [
    { value: "openrouter", label: "OpenRouter" },
    { value: "google", label: "Google AI" },
    { value: "openai", label: "OpenAI" },
    { value: "anthropic", label: "Anthropic" },
    { value: "litellm", label: "LiteLLM" },
    { value: "custom", label: "Custom" },
];

// Custom dropdown component styled like the VNB autocomplete
function ProviderDropdown({
    value,
    onChange,
    googleCredAvailable,
}: {
    value: AIProviderType;
    onChange: (value: string) => void;
    googleCredAvailable: boolean;
}) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const selectedLabel = PROVIDER_OPTIONS.find(opt => opt.value === value)?.label || value;

    const handleSelect = (providerValue: string) => {
        onChange(providerValue);
        setIsOpen(false);
    };

    return (
        <div className="space-y-2" ref={dropdownRef}>
            <Label>Provider</Label>
            <div className="relative">
                {/* Trigger Button */}
                <button
                    type="button"
                    onClick={() => setIsOpen(!isOpen)}
                    className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 hover:bg-accent/50 transition-colors"
                >
                    <span className="flex items-center gap-2">
                        <ProviderLogo provider={value} className="h-4 w-4" />
                        <span>{selectedLabel}</span>
                        {value === "google" && googleCredAvailable && (
                            <Check className="h-3.5 w-3.5 text-green-500" />
                        )}
                    </span>
                    <ChevronDown className={`h-4 w-4 opacity-50 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown Menu */}
                {isOpen && (
                    <div className="absolute top-full left-0 right-0 z-[9999] mt-1 bg-popover border rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {PROVIDER_OPTIONS.map((option) => {
                            const isSelected = option.value === value;
                            return (
                                <button
                                    key={option.value}
                                    type="button"
                                    className={`w-full px-3 py-2.5 text-left hover:bg-accent flex items-center gap-3 transition-colors ${isSelected ? 'bg-accent/50' : ''
                                        }`}
                                    onClick={() => handleSelect(option.value)}
                                >
                                    <span className="w-5 flex items-center justify-center">
                                        {isSelected && <Check className="h-4 w-4 text-primary" />}
                                    </span>
                                    <ProviderLogo provider={option.value} className="h-4 w-4" />
                                    <span className="flex-1">{option.label}</span>
                                    {option.value === "google" && googleCredAvailable && (
                                        <span className="text-xs text-green-500 font-medium">CLI ✓</span>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}

// Model type from API
interface AIModel {
    id: string;
    name: string;
    supports_vision?: boolean;
    supports_files?: boolean;
}

// Fuzzy match function - checks if query chars appear in order within target
function fuzzyMatch(query: string, target: string): boolean {
    const q = query.toLowerCase();
    const t = target.toLowerCase();

    // Simple contains check first
    if (t.includes(q)) return true;

    // Then fuzzy: check if all chars of query appear in order in target
    let qi = 0;
    for (let ti = 0; ti < t.length && qi < q.length; ti++) {
        if (t[ti] === q[qi]) qi++;
    }
    return qi === q.length;
}

// Model autocomplete component with two-stage search
// Stage 1: Show curated suggested models by default
// Stage 2: Search the full registry when user types
function ModelAutocomplete({
    value,
    onChange,
    models,
    requireVision,
    requireFiles,
    onCapabilitiesChange,
    providerType,
}: {
    value: string;
    onChange: (value: string) => void;
    models: AIModel[];
    requireVision?: boolean;
    requireFiles?: boolean;
    onCapabilitiesChange?: (vision: boolean, files: boolean) => void;
    providerType?: string;
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState(value);
    const [searchQuery, setSearchQuery] = useState("");
    const [isSearching, setIsSearching] = useState(false);
    const [searchResults, setSearchResults] = useState<AIModel[]>([]);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Sync inputValue with external value changes
    useEffect(() => {
        setInputValue(value);
    }, [value]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Debounced search against full registry
    useEffect(() => {
        // Clear previous timeout
        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }

        // Only search if we have a query and provider
        if (!searchQuery || searchQuery.length < 2 || !providerType) {
            setSearchResults([]);
            setIsSearching(false);
            return;
        }

        setIsSearching(true);

        // Debounce the search by 300ms
        searchTimeoutRef.current = setTimeout(async () => {
            try {
                const response = await api.admin.getAIModels(providerType, {
                    query: searchQuery,
                    supports_vision: requireVision ? true : undefined,
                    supports_files: requireFiles ? true : undefined,
                    limit: 15,
                });

                if (response.data?.models) {
                    setSearchResults(response.data.models as AIModel[]);
                }
            } catch (error) {
                console.error("Model search failed:", error);
                setSearchResults([]);
            } finally {
                setIsSearching(false);
            }
        }, 300);

        return () => {
            if (searchTimeoutRef.current) {
                clearTimeout(searchTimeoutRef.current);
            }
        };
    }, [searchQuery, providerType, requireVision, requireFiles]);

    // Pre-filter models by required capabilities
    const capabilityFilteredModels = models.filter(m => {
        if (requireVision && !m.supports_vision) return false;
        if (requireFiles && !m.supports_files) return false;
        return true;
    });

    // Determine which models to show
    const displayModels = useMemo(() => {
        // If we have search results from the registry, show those
        if (searchQuery.length >= 2 && searchResults.length > 0) {
            return searchResults;
        }

        // Otherwise filter the suggested models locally
        if (inputValue.length > 0) {
            return capabilityFilteredModels.filter(m =>
                fuzzyMatch(inputValue, m.id) || fuzzyMatch(inputValue, m.name)
            );
        }

        return capabilityFilteredModels;
    }, [inputValue, searchQuery, searchResults, capabilityFilteredModels]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setInputValue(newValue);
        setSearchQuery(newValue);
        onChange(newValue);
        setIsOpen(true);
    };

    const handleSelect = (model: AIModel) => {
        setInputValue(model.id);
        setSearchQuery("");
        onChange(model.id);
        setIsOpen(false);
        // Update capabilities based on selected model
        if (onCapabilitiesChange) {
            onCapabilitiesChange(model.supports_vision ?? false, model.supports_files ?? false);
        }
    };

    const handleFocus = () => {
        if (models.length > 0) {
            setIsOpen(true);
        }
    };

    const showDropdown = isOpen && (displayModels.length > 0 || isSearching);

    return (
        <div className="space-y-2" ref={dropdownRef}>
            <Label>Model</Label>
            <div className="relative">
                {/* Input Field */}
                <input
                    ref={inputRef}
                    type="text"
                    value={inputValue}
                    onChange={handleInputChange}
                    onFocus={handleFocus}
                    placeholder={models.length > 0 ? "Search models or enter custom ID..." : "Enter model ID..."}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                />

                {/* Dropdown indicator / loading spinner */}
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                    {isSearching && (
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    )}
                    {models.length > 0 && (
                        <button
                            type="button"
                            onClick={() => setIsOpen(!isOpen)}
                            className="p-1 hover:bg-accent rounded transition-colors"
                        >
                            <ChevronDown className={`h-4 w-4 opacity-50 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                        </button>
                    )}
                </div>

                {/* Dropdown Menu */}
                {showDropdown && (
                    <div className="absolute top-full left-0 right-0 z-[9999] mt-1 bg-popover border rounded-md shadow-lg max-h-48 overflow-y-auto">
                        {searchQuery.length >= 2 && searchResults.length > 0 && (
                            <div className="px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/50">
                                🔍 Search results from registry
                            </div>
                        )}
                        {displayModels.map((model) => {
                            const isSelected = model.id === inputValue;
                            return (
                                <button
                                    key={model.id}
                                    type="button"
                                    className={`w-full px-3 py-2.5 text-left hover:bg-accent flex items-center gap-3 transition-colors ${isSelected ? 'bg-accent/50' : ''
                                        }`}
                                    onClick={() => handleSelect(model)}
                                >
                                    <span className="w-5 flex items-center justify-center">
                                        {isSelected && <Check className="h-4 w-4 text-primary" />}
                                    </span>
                                    <span className="flex-1 truncate">{model.name}</span>
                                    <span className="flex items-center gap-1 text-muted-foreground">
                                        {model.supports_vision && <span title="Vision">🖼️</span>}
                                        {model.supports_files && <span title="Files">📁</span>}
                                    </span>
                                </button>
                            );
                        })}
                        {isSearching && (
                            <div className="px-3 py-2.5 text-sm text-muted-foreground flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Searching registry...
                            </div>
                        )}
                    </div>
                )}
            </div>
            {inputValue && displayModels.length === 0 && models.length > 0 && !isSearching && (
                <p className="text-xs text-muted-foreground">
                    Using custom model: <span className="font-medium text-foreground">{inputValue}</span>
                </p>
            )}
        </div>
    );
}

export function AIConfigSection() {
    const queryClient = useQueryClient();
    const [showAddDialog, setShowAddDialog] = useState(false);
    const [testingId, setTestingId] = useState<number | null>(null);

    // Fetch AI configs
    const { data: configsResponse, isLoading } = useQuery({
        queryKey: ["admin", "ai-config"],
        queryFn: api.admin.getAIConfigs,
    });

    const configs = configsResponse?.data?.configs || [];

    // Test mutation
    const testMutation = useMutation({
        mutationFn: (configId: number) => api.admin.testAIConfig(configId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin", "ai-config"] });
        },
        onSettled: () => {
            setTestingId(null);
        },
    });

    // Delete mutation
    const deleteMutation = useMutation({
        mutationFn: (configId: number) => api.admin.deleteAIConfig(configId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin", "ai-config"] });
        },
    });

    // Toggle enabled mutation
    const toggleMutation = useMutation({
        mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
            api.admin.updateAIConfig(id, { is_enabled: enabled }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin", "ai-config"] });
        },
    });

    const handleTest = (configId: number) => {
        setTestingId(configId);
        testMutation.mutate(configId);
    };

    const enabledCount = configs.filter((c) => c.is_enabled).length;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-primary" />
                    AI Configuration
                    {enabledCount > 0 && (
                        <Badge variant="secondary" className="ml-2">
                            {enabledCount} active
                        </Badge>
                    )}
                </CardTitle>
                <CardDescription>
                    Configure AI providers for data extraction. Providers are tried in order
                    with automatic fallback on rate limits.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="flex items-center justify-center py-8 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin mr-2" />
                        Loading configurations...
                    </div>
                ) : configs.length === 0 ? (
                    <div className="text-center py-8 border border-dashed border-border rounded-lg">
                        <Brain className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                        <p className="text-muted-foreground mb-4">
                            No AI providers configured. Add a provider to enable AI extraction.
                        </p>
                        <Button onClick={() => setShowAddDialog(true)}>
                            <Plus className="h-4 w-4 mr-2" />
                            Add Provider
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {configs.map((config, index) => (
                            <ProviderCard
                                key={config.id}
                                config={config}
                                index={index}
                                isTesting={testingId === config.id}
                                onTest={() => handleTest(config.id)}
                                onDelete={() => deleteMutation.mutate(config.id)}
                                onToggle={(enabled) =>
                                    toggleMutation.mutate({ id: config.id, enabled })
                                }
                            />
                        ))}
                        <Button
                            variant="outline"
                            className="w-full mt-4"
                            onClick={() => setShowAddDialog(true)}
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            Add Provider
                        </Button>
                    </div>
                )}
            </CardContent>

            {/* Add Provider Dialog */}
            <AddProviderDialog
                open={showAddDialog}
                onOpenChange={setShowAddDialog}
                onSuccess={() => {
                    setShowAddDialog(false);
                    queryClient.invalidateQueries({ queryKey: ["admin", "ai-config"] });
                }}
            />
        </Card>
    );
}

function ProviderCard({
    config,
    index,
    isTesting,
    onTest,
    onDelete,
    onToggle,
}: {
    config: AIProviderConfig;
    index: number;
    isTesting: boolean;
    onTest: () => void;
    onDelete: () => void;
    onToggle: (enabled: boolean) => void;
}) {
    const info = PROVIDER_INFO[config.provider_type] || PROVIDER_INFO.custom;

    return (
        <div
            className={`flex items-center gap-3 p-3 rounded-lg border ${config.is_enabled
                ? "border-border bg-card"
                : "border-border/50 bg-muted/30 opacity-60"
                }`}
        >
            {/* Drag handle */}
            <div className="cursor-grab text-muted-foreground hover:text-foreground">
                <GripVertical className="h-4 w-4" />
            </div>

            {/* Priority number */}
            <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                {index + 1}
            </div>

            {/* Provider icon & info */}
            <div className={`p-2 rounded-lg ${info.color}`}>
                <ProviderLogo provider={config.provider_type} className="h-5 w-5" />
            </div>

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{config.name}</span>
                    {config.is_subscription && (
                        <span title="Subscription"><Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" /></span>
                    )}
                    {STATUS_ICONS[config.status]}
                </div>
                <div className="text-xs text-muted-foreground flex items-center gap-2">
                    <span>{config.model}</span>
                    <span className="text-muted-foreground/50">•</span>
                    <span className="flex items-center gap-1">
                        {config.supports_text && (
                            <span title="Text"><FileText className="h-3 w-3" /></span>
                        )}
                        {config.supports_vision && (
                            <span title="Vision"><Image className="h-3 w-3" /></span>
                        )}
                        {config.supports_files && (
                            <span title="Files"><File className="h-3 w-3" /></span>
                        )}
                    </span>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onTest}
                    disabled={isTesting}
                    title="Test connection"
                >
                    {isTesting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <RefreshCw className="h-4 w-4" />
                    )}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onDelete}
                    className="text-destructive hover:text-destructive"
                    title="Delete"
                >
                    <Trash2 className="h-4 w-4" />
                </Button>
                <Button
                    variant={config.is_enabled ? "default" : "outline"}
                    size="sm"
                    onClick={() => onToggle(!config.is_enabled)}
                    title={config.is_enabled ? "Disable" : "Enable"}
                >
                    {config.is_enabled ? "On" : "Off"}
                </Button>
            </div>
        </div>
    );
}

function AddProviderDialog({
    open,
    onOpenChange,
    onSuccess,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSuccess: () => void;
}) {
    const [providerType, setProviderType] = useState<AIProviderType>("openrouter");
    const [name, setName] = useState("");
    const [nameManuallyEdited, setNameManuallyEdited] = useState(false);
    const [apiKey, setApiKey] = useState("");
    const [apiUrl, setApiUrl] = useState("");
    const [model, setModel] = useState("");
    const [supportsVision, setSupportsVision] = useState(true);
    const [supportsFiles, setSupportsFiles] = useState(false);
    const [authType, setAuthType] = useState<"api_key" | "oauth">("api_key");
    const [isOAuthPending, setIsOAuthPending] = useState(false);
    const [oauthError, setOauthError] = useState<string | null>(null);
    const queryClient = useQueryClient();
    const { toast } = useToast();
    const { showError } = useErrorToast();

    // Detect CLI credentials when dialog opens
    const { data: credsData } = useQuery({
        queryKey: ["admin", "detect-credentials"],
        queryFn: api.admin.detectCredentials,
        enabled: open,
    });

    const detectedCreds = credsData?.data?.credentials || {};
    const googleCredAvailable = detectedCreds.google?.available || false;
    const googleCredEmail = detectedCreds.google?.email;

    // Fetch models for selected provider
    const { data: modelsData } = useQuery({
        queryKey: ["admin", "ai-models", providerType],
        queryFn: () => api.admin.getAIModels(providerType),
        enabled: open,
    });

    const models = modelsData?.data?.models || [];
    const defaultUrl = modelsData?.data?.default_url || "";

    // Generate auto name based on provider, model, and auth type
    const generateAutoName = () => {
        const providerName = PROVIDER_INFO[providerType]?.name || providerType;
        const modelName = models.find(m => m.id === model)?.name || model;

        if (providerType === "google" && authType === "oauth") {
            return googleCredEmail
                ? `${providerName} (${googleCredEmail})`
                : `${providerName} (OAuth)`;
        }

        if (modelName) {
            return `${providerName} - ${modelName}`;
        }

        return providerName;
    };

    // Update auto-generated name when dependencies change (if not manually edited)
    useEffect(() => {
        if (!nameManuallyEdited && open) {
            const autoName = generateAutoName();
            setName(autoName);
        }
    }, [providerType, model, authType, googleCredEmail, nameManuallyEdited, open, models]);

    // When provider changes
    const handleProviderChange = (v: string) => {
        const provider = v as AIProviderType;
        setProviderType(provider);
        setModel("");
        setNameManuallyEdited(false); // Reset to allow auto-naming

        // Default to OAuth for Google if credentials are available
        if (provider === "google" && googleCredAvailable) {
            setAuthType("oauth");
        } else {
            setAuthType("api_key");
        }
    };

    // Handle name field changes
    const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setName(newValue);
        setNameManuallyEdited(newValue.length > 0);
    };

    // Handle name field blur - regenerate if empty
    const handleNameBlur = () => {
        if (name.trim() === "") {
            setNameManuallyEdited(false);
            setName(generateAutoName());
        }
    };

    // Handle auth type change
    const handleAuthTypeChange = (newAuthType: "api_key" | "oauth") => {
        setAuthType(newAuthType);
        setNameManuallyEdited(false); // Allow name to update with new auth type
        setOauthError(null);
    };

    // Handle OAuth flow start
    const handleStartOAuthFlow = async () => {
        setIsOAuthPending(true);
        setOauthError(null);

        try {
            // Start the OAuth flow - get auth URL
            const response = await api.admin.startGoogleOAuth();

            if (!response.success || !response.data?.auth_url) {
                throw new Error(response.message || "Failed to start OAuth flow");
            }

            const authUrl = response.data.auth_url;

            // Open popup for OAuth
            const popup = window.open(
                authUrl,
                "google_oauth",
                "width=500,height=600,scrollbars=yes,resizable=yes"
            );

            if (!popup) {
                throw new Error("Popup was blocked. Please allow popups for this site.");
            }

            // Poll for popup closure and refresh credentials
            const pollInterval = setInterval(async () => {
                if (popup.closed) {
                    clearInterval(pollInterval);
                    setIsOAuthPending(false);

                    // Refresh credentials to check if OAuth succeeded
                    await queryClient.invalidateQueries({ queryKey: ["admin", "detect-credentials"] });
                }
            }, 500);

            // Set a timeout to stop polling after 5 minutes
            setTimeout(() => {
                clearInterval(pollInterval);
                if (!popup.closed) {
                    popup.close();
                }
                setIsOAuthPending(false);
            }, 5 * 60 * 1000);

        } catch (error) {
            console.error("OAuth flow failed:", error);
            setOauthError(error instanceof Error ? error.message : "OAuth flow failed");
            setIsOAuthPending(false);
        }
    };

    // Create mutation
    const createMutation = useMutation({
        mutationFn: (config: AIConfigCreate) => api.admin.createAIConfig(config),
        onSuccess: () => {
            toast({
                title: "Provider Added",
                description: `Successfully added ${name || generateAutoName()}`,
            });
            onSuccess();
            // Reset form
            setName("");
            setNameManuallyEdited(false);
            setApiKey("");
            setApiUrl("");
            setModel("");
            setAuthType("api_key");
            setTestResult(null);
        },
        onError: (error) => {
            showError(error, {
                title: "Failed to Add Provider",
                fallbackMessage: "Could not save the AI provider configuration. Please try again.",
            });
        },
    });

    // Logout OAuth mutation
    const logoutMutation = useMutation({
        mutationFn: () => api.admin.logoutGoogleOAuth(),
        onSuccess: () => {
            // Refresh credentials detection
            queryClient.invalidateQueries({ queryKey: ["admin", "detect-credentials"] });
        },
    });

    // Test connection state
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [isTesting, setIsTesting] = useState(false);

    const handleTestConnection = async () => {
        if (!model) {
            setTestResult({ success: false, message: "Please select a model first" });
            return;
        }

        // Basic validation first
        if (authType === "api_key" && !apiKey && providerType !== "litellm" && providerType !== "custom") {
            setTestResult({ success: false, message: "API key is required" });
            return;
        }

        if (authType === "oauth" && !googleCredAvailable) {
            setTestResult({ success: false, message: "OAuth credentials not available. Please authenticate first." });
            return;
        }

        setIsTesting(true);
        setTestResult(null);

        try {
            // Call the real test endpoint
            const response = await api.admin.testAIConfigPreview({
                provider_type: providerType,
                auth_type: authType === "oauth" ? "cli" : "api_key",
                model: model,
                api_key: authType === "api_key" ? apiKey : undefined,
                api_url: apiUrl || defaultUrl || undefined,
            });

            if (response.success) {
                const data = response.data;
                setTestResult({
                    success: true,
                    message: response.message || `✓ Model responded: "${data?.response || 'OK'}" (${data?.elapsed_ms}ms)`,
                });
            } else {
                setTestResult({
                    success: false,
                    message: response.message || "Connection test failed",
                });
            }
        } catch (error) {
            console.error("Test connection failed:", error);
            setTestResult({
                success: false,
                message: error instanceof Error ? error.message : "Test failed - check console for details"
            });
        } finally {
            setIsTesting(false);
        }
    };

    const handleSubmit = () => {
        // Use generated name if empty
        const finalName = name.trim() || generateAutoName();

        if (!finalName || !model) {
            showError(new Error("Name and model are required"), {
                title: "Validation Error",
            });
            return;
        }

        const config = {
            name: finalName,
            provider_type: providerType,
            auth_type: authType === "oauth" ? "cli" : "api_key", // CLI uses OAuth credentials from Gemini CLI
            model: model,
            api_key: authType === "api_key" ? apiKey : undefined,
            api_url: apiUrl || defaultUrl || undefined,
            supports_text: true,
            supports_vision: supportsVision,
            supports_files: supportsFiles,
        };

        createMutation.mutate(config as AIConfigCreate);
    };

    const needsApiUrl = providerType === "litellm" || providerType === "custom";
    const needsApiKey = authType === "api_key";
    const showAuthTypeToggle = providerType === "google"; // Only Google supports OAuth currently

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>Add AI Provider</DialogTitle>
                    <DialogDescription>
                        Configure a new AI provider for data extraction.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Provider Type */}
                    <ProviderDropdown
                        value={providerType}
                        onChange={handleProviderChange}
                        googleCredAvailable={googleCredAvailable}
                    />

                    {/* Authentication Type Toggle (for Google) */}
                    {showAuthTypeToggle && (
                        <div className="space-y-3">
                            <Label>Authentication Method</Label>
                            <div className="grid grid-cols-2 gap-2">
                                {/* OAuth Option */}
                                <button
                                    type="button"
                                    onClick={() => handleAuthTypeChange("oauth")}
                                    className={`p-3 rounded-lg border text-left transition-all ${authType === "oauth"
                                        ? "border-primary bg-primary/10 ring-2 ring-primary/20"
                                        : "border-border hover:border-primary/50 hover:bg-accent/50"
                                        }`}
                                >
                                    <div className="flex items-center gap-2 font-medium mb-1">
                                        {googleCredAvailable ? (
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                        ) : (
                                            <RefreshCw className="h-4 w-4" />
                                        )}
                                        OAuth / CLI
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        {googleCredAvailable
                                            ? `Uses existing Gemini CLI credentials (${googleCredEmail})`
                                            : "Authenticate via Google OAuth (like Gemini CLI)"
                                        }
                                    </p>
                                </button>

                                {/* API Key Option */}
                                <button
                                    type="button"
                                    onClick={() => handleAuthTypeChange("api_key")}
                                    className={`p-3 rounded-lg border text-left transition-all ${authType === "api_key"
                                        ? "border-primary bg-primary/10 ring-2 ring-primary/20"
                                        : "border-border hover:border-primary/50 hover:bg-accent/50"
                                        }`}
                                >
                                    <div className="flex items-center gap-2 font-medium mb-1">
                                        <Key className="h-4 w-4" />
                                        API Key
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Use a Google AI Studio API key
                                    </p>
                                </button>
                            </div>

                            {/* OAuth not available - show setup instructions */}
                            {authType === "oauth" && !googleCredAvailable && (
                                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                                    <div className="flex items-center gap-2 text-amber-500 font-medium mb-1">
                                        <AlertTriangle className="h-4 w-4" />
                                        OAuth not yet configured
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                        Authenticate with your Google account to use Gemini. This uses the same OAuth flow as the Gemini CLI.
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1 opacity-75">
                                        💡 Your existing Gemini CLI credentials will work automatically if detected.
                                    </p>
                                    {oauthError && (
                                        <p className="text-xs text-red-500 mt-2">
                                            ⚠️ {oauthError}
                                        </p>
                                    )}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="mt-2"
                                        onClick={handleStartOAuthFlow}
                                        disabled={isOAuthPending}
                                    >
                                        {isOAuthPending ? (
                                            <>
                                                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                                                Authenticating...
                                            </>
                                        ) : (
                                            <>
                                                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                                                Start OAuth Flow
                                            </>
                                        )}
                                    </Button>
                                </div>
                            )}

                            {/* OAuth available - show account info */}
                            {authType === "oauth" && googleCredAvailable && (
                                <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                                    <div className="flex items-center justify-between mb-1">
                                        <div className="flex items-center gap-2 text-green-500 font-medium">
                                            <CheckCircle2 className="h-4 w-4" />
                                            Gemini CLI credentials detected
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                                            onClick={() => logoutMutation.mutate()}
                                            disabled={logoutMutation.isPending}
                                        >
                                            {logoutMutation.isPending ? (
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                            ) : (
                                                "Use different account"
                                            )}
                                        </Button>
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                        Using account: <span className="font-medium text-foreground">{googleCredEmail}</span>
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        No API key needed - uses your Google account's Gemini quota.
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Name */}
                    <div className="space-y-2">
                        <Label>Display Name</Label>
                        <Input
                            placeholder={generateAutoName()}
                            value={name}
                            onChange={handleNameChange}
                            onBlur={handleNameBlur}
                        />
                        <p className="text-xs text-muted-foreground">
                            Auto-generated if left empty
                        </p>
                    </div>

                    {/* API URL (for LiteLLM/Custom) */}
                    {needsApiUrl && (
                        <div className="space-y-2">
                            <Label>API URL</Label>
                            <Input
                                placeholder="https://your-litellm-server.com/v1"
                                value={apiUrl}
                                onChange={(e) => setApiUrl(e.target.value)}
                            />
                        </div>
                    )}

                    {/* API Key - only shown when using API key auth */}
                    {needsApiKey && (
                        <div className="space-y-2">
                            <Label className="flex items-center gap-2">
                                <Key className="h-3.5 w-3.5" />
                                API Key
                            </Label>
                            <Input
                                type="password"
                                placeholder={providerType === "google" ? "AIza..." : "sk-..."}
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                            />
                        </div>
                    )}

                    {/* Model Selection */}
                    <ModelAutocomplete
                        value={model}
                        onChange={(newModel) => {
                            setModel(newModel);
                            setNameManuallyEdited(false); // Allow name to update with new model
                        }}
                        models={models}
                        requireVision={supportsVision}
                        requireFiles={supportsFiles}
                        providerType={providerType}
                        onCapabilitiesChange={(vision, files) => {
                            setSupportsVision(vision);
                            setSupportsFiles(files);
                        }}
                    />

                    {/* Capabilities */}
                    <div className="space-y-3">
                        <Label>Capabilities</Label>
                        <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 text-sm">
                                <Checkbox
                                    checked={supportsVision}
                                    onCheckedChange={(checked) => setSupportsVision(!!checked)}
                                />
                                <Image className="h-4 w-4" />
                                Vision
                            </label>
                            <label className="flex items-center gap-2 text-sm">
                                <Checkbox
                                    checked={supportsFiles}
                                    onCheckedChange={(checked) => setSupportsFiles(!!checked)}
                                />
                                <File className="h-4 w-4" />
                                PDF/Files
                            </label>
                        </div>
                    </div>
                </div>

                {/* Test Result */}
                {testResult && (
                    <div className={`p-3 rounded-lg border ${testResult.success
                        ? "border-green-500/30 bg-green-500/10"
                        : "border-red-500/30 bg-red-500/10"
                        }`}>
                        <p className={`text-sm ${testResult.success ? "text-green-500" : "text-red-500"}`}>
                            {testResult.success ? "✓" : "✗"} {testResult.message}
                        </p>
                    </div>
                )}

                <DialogFooter className="gap-2 sm:gap-0">
                    <div className="flex gap-2 w-full sm:w-auto">
                        <Button
                            variant="outline"
                            onClick={handleTestConnection}
                            disabled={!model || isTesting}
                            className="flex-1 sm:flex-none"
                        >
                            {isTesting ? (
                                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            ) : (
                                <Zap className="h-4 w-4 mr-2" />
                            )}
                            Test
                        </Button>
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                    </div>
                    <Button
                        type="button"
                        onClick={handleSubmit}
                        disabled={!model || createMutation.isPending || (authType === "api_key" && !apiKey && providerType !== "litellm" && providerType !== "custom")}
                    >
                        {createMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <Plus className="h-4 w-4 mr-2" />
                        )}
                        Add Provider
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
