import { useState, useRef, useEffect, useMemo } from "react";
import { useToast } from "@/hooks/use-toast";
import { useErrorToast } from "@/hooks/use-error-toast";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    api,
    type AIProviderConfig,
    type AIProviderType,
    type AIConfigCreate,
    type AIConfigUpdate,
    type ThinkingCapability,
    type AIAuthType,
} from "@/lib/api";
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
import { Switch } from "@/components/ui/switch";
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

// Static list of available provider types (must match backend PROVIDER_REGISTRY)
const PROVIDER_TYPES = ["openrouter", "litellm", "custom"] as const;

// Static provider info map (must match backend provider get_provider_info())
const PROVIDER_INFO_MAP: Record<string, { name: string; color: string; icon_svg: string; icon_emoji?: string }> = {
    openrouter: {
        name: "OpenRouter",
        color: "bg-purple-500/20 text-purple-500",
        icon_svg: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3.10913 12.07C3.65512 12.07 5.76627 11.5988 6.85825 10.98C7.95023 10.3612 7.95023 10.3612 10.207 8.75965C13.0642 6.73196 15.0845 7.41088 18.3968 7.41088" fill="currentColor"/><path d="M3.10913 12.07C3.65512 12.07 5.76627 11.5988 6.85825 10.98C7.95023 10.3612 7.95023 10.3612 10.207 8.75965C13.0642 6.73196 15.0845 7.41088 18.3968 7.41088" stroke="currentColor" stroke-width="3.27593"/><path d="M21.6 7.43108L16.0037 10.6622V4.20001L21.6 7.43108Z" fill="currentColor" stroke="currentColor" stroke-width="0.0363992"/><path d="M3 12.072C3.54599 12.072 5.65714 12.5432 6.74912 13.162C7.8411 13.7808 7.8411 13.7808 10.0978 15.3823C12.9551 17.41 14.9753 16.7311 18.2877 16.7311" fill="currentColor"/><path d="M3 12.072C3.54599 12.072 5.65714 12.5432 6.74912 13.162C7.8411 13.7808 7.8411 13.7808 10.0978 15.3823C12.9551 17.41 14.9753 16.7311 18.2877 16.7311" stroke="currentColor" stroke-width="3.27593"/><path d="M21.4909 16.7109L15.8945 13.4798V19.942L21.4909 16.7109Z" fill="currentColor" stroke="currentColor" stroke-width="0.0363992"/></svg>`,
    },
    litellm: {
        name: "LiteLLM Proxy",
        color: "bg-cyan-500/20 text-cyan-500",
        icon_svg: "",
        icon_emoji: "🚅",
    },
    custom: {
        name: "Custom API",
        color: "bg-gray-500/20 text-gray-400",
        icon_svg: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/></svg>`,
    },
};

// Fallback provider info when backend hasn't loaded yet
const FALLBACK_PROVIDER_INFO = {
    name: "Unknown",
    description: "",
    color: "bg-gray-500/20 text-gray-400",
    icon_svg: "",
    icon_emoji: "🔧",
};

// Provider icon component using inline SVG or emoji from backend
function ProviderIcon({ iconSvg, iconEmoji, className = "h-4 w-4" }: {
    iconSvg?: string;
    iconEmoji?: string;
    className?: string;
}) {
    if (iconSvg) {
        // Inject width/height 100% into SVG for proper scaling
        const scaledSvg = iconSvg.replace(
            /^<svg/,
            '<svg style="width:100%;height:100%"'
        );
        return (
            <span
                className={className}
                style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
                dangerouslySetInnerHTML={{ __html: scaledSvg }}
            />
        );
    }
    // Use emoji if provided, otherwise default wrench emoji
    return <span className={`${className} flex items-center justify-center text-lg`}>{iconEmoji || "🔧"}</span>;
}

// Status icons
const STATUS_ICONS: Record<string, React.ReactNode> = {
    active: <CheckCircle2 className="h-4 w-4 text-green-500" />,
    disabled: <XCircle className="h-4 w-4 text-muted-foreground" />,
    rate_limited: <Clock className="h-4 w-4 text-amber-500" />,
    unhealthy: <AlertTriangle className="h-4 w-4 text-red-500" />,
    untested: <RefreshCw className="h-4 w-4 text-muted-foreground" />,
};

// Simple provider dropdown using static provider list
function ProviderDropdown({
    value,
    onChange,
    currentInfo,
}: {
    value: AIProviderType;
    onChange: (value: string) => void;
    currentInfo: { name: string; icon_svg: string; icon_emoji?: string };
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
                        <ProviderIcon iconSvg={currentInfo.icon_svg} iconEmoji={currentInfo.icon_emoji} className="h-4 w-4" />
                        <span>{currentInfo.name}</span>
                    </span>
                    <ChevronDown className={`h-4 w-4 opacity-50 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown Menu */}
                {isOpen && (
                    <div className="absolute top-full left-0 right-0 z-[9999] mt-1 bg-popover border rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {PROVIDER_TYPES.map((providerType) => {
                            const isSelected = providerType === value;
                            return (
                                <button
                                    key={providerType}
                                    type="button"
                                    className={`w-full px-3 py-2.5 text-left hover:bg-accent flex items-center gap-3 transition-colors ${isSelected ? 'bg-accent/50' : ''
                                        }`}
                                    onClick={() => handleSelect(providerType)}
                                >
                                    <span className="w-5 flex items-center justify-center">
                                        {isSelected && <Check className="h-4 w-4 text-primary" />}
                                    </span>
                                    <span className="flex-1 capitalize">{providerType}</span>
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
    thinking_capability?: ThinkingCapability;
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
    onCapabilitiesChange?: (vision: boolean, files: boolean, thinking?: ThinkingCapability) => void;
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
            onCapabilitiesChange(
                model.supports_vision ?? false,
                model.supports_files ?? false,
                model.thinking_capability
            );
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

// Reusable Provider Dialog for Adding/Editing
function ProviderDialog({
    open,
    onOpenChange,
    onSuccess,
    initialConfig,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSuccess: () => void;
    initialConfig?: AIProviderConfig | null;
}) {
    const isEditMode = !!initialConfig;
    const [providerType, setProviderType] = useState<AIProviderType>("openrouter");
    const [name, setName] = useState("");
    const [nameManuallyEdited, setNameManuallyEdited] = useState(false);
    const [apiKey, setApiKey] = useState("");
    const [apiUrl, setApiUrl] = useState("");
    const [model, setModel] = useState("");
    const [supportsVision, setSupportsVision] = useState(true);
    const [supportsFiles, setSupportsFiles] = useState(false);

    // Thinking Config State
    const [thinkingCapability, setThinkingCapability] = useState<ThinkingCapability | null>(null);
    const [thinkingEnabled, setThinkingEnabled] = useState(false);
    const [thinkingLevel, setThinkingLevel] = useState<string>("medium");
    const [thinkingBudget, setThinkingBudget] = useState<number>(0);

    // Manual Thinking Config for Custom Models
    const [manualThinkingMethod, setManualThinkingMethod] = useState<"none" | "level" | "budget">("none");

    const [authType] = useState<AIAuthType>("api_key");
    const { toast } = useToast();
    const { showError } = useErrorToast();

    // Initialize form with initialConfig when available
    useEffect(() => {
        if (initialConfig && open) {
            setProviderType(initialConfig.provider_type);
            setName(initialConfig.name);
            setNameManuallyEdited(true);
            setModel(initialConfig.model);
            setApiUrl(initialConfig.api_url || "");
            setSupportsVision(initialConfig.supports_vision);
            setSupportsFiles(initialConfig.supports_files);
            // NOTE: We cannot pre-fill API Key for security reasons
            setApiKey("");

            // Initialize Thinking Configuration (uses reasoning_level/reasoning_budget in API)
            const params = initialConfig.model_parameters || {};
            if (params.reasoning_level) {
                setThinkingEnabled(true);
                setThinkingLevel(params.reasoning_level);
                // If we don't have capability info yet, assume manual level or native level
                // We'll let the UI resolve based on capability later, but for state:
                if (!thinkingCapability) setManualThinkingMethod("level");
            } else if (params.reasoning_budget) {
                setThinkingEnabled(true);
                setThinkingBudget(params.reasoning_budget);
                if (!thinkingCapability) setManualThinkingMethod("budget");
            } else {
                setThinkingEnabled(false);
                setManualThinkingMethod("none");
            }

        } else if (!initialConfig && open) {
            // Reset to defaults for Create mode
            setProviderType("openrouter");
            setName("");
            setNameManuallyEdited(false);
            setModel("");
            setApiUrl("");
            setApiKey("");
            setSupportsVision(true);
            setSupportsFiles(true);  // Default to true, will be updated by model selection
            setThinkingEnabled(false);
            setThinkingLevel("medium");
            setThinkingBudget(0);
            setManualThinkingMethod("none");
        }
    }, [initialConfig, open]);

    // Enforce mandatory thinking if model capability requires it
    useEffect(() => {
        if (thinkingCapability?.can_disable === false && !thinkingEnabled) {
            setThinkingEnabled(true);
        }
    }, [thinkingCapability, thinkingEnabled]);

    // Fetch available providers (for dynamic UI)
    // Fetch models for selected provider (also returns provider_info)
    const { data: modelsData } = useQuery({
        queryKey: ["admin", "ai-models", providerType],
        queryFn: () => api.admin.getAIModels(providerType),
        enabled: open,
    });

    const models = modelsData?.data?.models || [];
    const defaultUrl = modelsData?.data?.default_url || "";
    const defaultModel = modelsData?.data?.default_model || "";
    const reasoningOptions = modelsData?.data?.reasoning_options || null;
    const providerInfo = modelsData?.data?.provider_info || FALLBACK_PROVIDER_INFO;

    // Auto-fill default model when provider changes (create mode only)
    useEffect(() => {
        if (!isEditMode && open && defaultModel && !model) {
            setModel(defaultModel);
        }
    }, [defaultModel, open, isEditMode, model]);

    // Auto-sync capabilities from model metadata when models are loaded
    // This ensures stored configs get updated to match current model capabilities
    useEffect(() => {
        if (open && model && models.length > 0) {
            const selectedModel = models.find(m => m.id === model);
            if (selectedModel) {
                setSupportsVision(selectedModel.supports_vision ?? false);
                setSupportsFiles(selectedModel.supports_files ?? false);
                if (selectedModel.thinking_capability) {
                    setThinkingCapability(selectedModel.thinking_capability);
                }
            }
        }
    }, [open, model, models]);

    // Generate auto name based on provider and model
    const generateAutoName = () => {
        const providerName = providerInfo?.name || providerType;
        const modelName = models.find(m => m.id === model)?.name || model;

        if (modelName) {
            return `${providerName} - ${modelName}`;
        }

        return providerName;
    };

    // Update auto-generated name when dependencies change (if not manually edited)
    useEffect(() => {
        if (!nameManuallyEdited && open && !isEditMode) {
            const autoName = generateAutoName();
            setName(autoName);
        }
    }, [providerType, model, nameManuallyEdited, open, models, isEditMode]);

    // When provider changes
    const handleProviderChange = (v: string) => {
        const provider = v as AIProviderType;
        setProviderType(provider);
        setModel("");
        if (!isEditMode) setNameManuallyEdited(false); // Reset to allow auto-naming in create mode
    };

    // Handle name field changes
    const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setName(newValue);
        setNameManuallyEdited(newValue.length > 0);
    };

    // Handle name field blur - regenerate if empty
    const handleNameBlur = () => {
        if (name.trim() === "" && !isEditMode) {
            setNameManuallyEdited(false);
            setName(generateAutoName());
        }
    };

    // Create mutation
    const createMutation = useMutation({
        mutationFn: (config: AIConfigCreate) => api.admin.createAIConfig(config),
        onSuccess: async (response) => {
            const newConfig = response.data;

            // If tested successfully, verify immediately
            if (testResult?.success && newConfig?.id) {
                try {
                    await api.admin.testAIConfig(newConfig.id);
                } catch (e) {
                    console.error("Auto-verification failed:", e);
                }
            }

            toast({
                title: "Provider Added",
                description: `Successfully added ${name || generateAutoName()}`,
            });
            onSuccess();
            setTestResult(null);
        },
        onError: (error) => {
            showError(error, {
                title: "Failed to Add Provider",
                fallbackMessage: "Could not save the AI provider configuration. Please try again.",
            });
        },
    });

    // Update mutation
    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: AIConfigUpdate }) =>
            api.admin.updateAIConfig(id, data),
        onSuccess: async () => {
            // If tested successfully and we have an ID, re-verify
            if (testResult?.success && initialConfig?.id) {
                try {
                    await api.admin.testAIConfig(initialConfig.id);
                } catch (e) {
                    console.error("Auto-verification failed:", e);
                }
            }

            toast({
                title: "Provider Updated",
                description: `Successfully updated ${name}`,
            });
            onSuccess();
            setTestResult(null);
        },
        onError: (error) => {
            showError(error, {
                title: "Failed to Update Provider",
                fallbackMessage: "Could not update the AI provider configuration. Please try again.",
            });
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

        // Basic validation first - API key needed if not existing or if user entered a new one
        // If editing and key field is empty, backend uses existing key. But for testing PREVIEW we might need it?
        // Actually, testAIConfigPreview sends what we have. API might need logic to use stored key if not provided?
        // `testAIConfigPreview` endpoint doesn't know about existing config ID, so it can't use stored key.
        // So validation: If editing and no new key entered -> we can't fully test PREVIEW unless backend supports it or we use the specific test endpoint for ID.
        // BUT `testAIConfigPreview` is stateless.
        // If isEditMode, we can perhaps use `api.admin.testAIConfig(id)` if NO changes were made? No, we want to test NEW settings.
        // LIMITATION: Can't test "preview" with hidden stored key.
        // Workaround: If editing and no key provided, warn user "Enter API Key to test connection" or similar, OR trust the user knows it works.
        // However, the `testAIConfig` endpoint (by ID) tests the SAVED config.

        // Let's rely on standard validation.
        if (authType === "api_key" && !apiKey && providerType !== "litellm" && providerType !== "custom") {
            // Special exemption: If editing, maybe they didn't change the key. 
            // But we can't test "preview" without the key.
            if (isEditMode) {
                setTestResult({ success: false, message: "Please re-enter API Key to test connection changes" });
                return;
            }
            setTestResult({ success: false, message: "API key is required" });
            return;
        }



        setIsTesting(true);
        setTestResult(null);

        try {
            // Build model_parameters for the test
            const testModelParameters: Record<string, any> = {};
            if (thinkingEnabled && reasoningOptions) {
                const effectiveMethod = manualThinkingMethod !== "none"
                    ? manualThinkingMethod
                    : (reasoningOptions.method === "budget" ? "budget" : "level");

                if (effectiveMethod === "budget") {
                    testModelParameters.reasoning_budget = thinkingBudget;
                } else if (effectiveMethod === "level") {
                    testModelParameters.reasoning_level = thinkingLevel;
                }
            }

            // Call the real test endpoint
            const response = await api.admin.testAIConfigPreview({
                provider_type: providerType,
                auth_type: "api_key",
                model: model,
                api_key: apiKey,
                api_url: apiUrl || defaultUrl || undefined,
                model_parameters: Object.keys(testModelParameters).length > 0 ? testModelParameters : undefined,
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

        const modelParameters: Record<string, any> = {};

        // Only add reasoning params for providers that support it (reasoningOptions not null)
        if (thinkingEnabled && reasoningOptions) {
            // Determine which method to use
            const effectiveMethod = manualThinkingMethod !== "none"
                ? manualThinkingMethod
                : (reasoningOptions.method === "budget" ? "budget" : "level");

            if (effectiveMethod === "budget") {
                // Token budget approach
                modelParameters.reasoning_budget = thinkingBudget;
            } else if (effectiveMethod === "level") {
                // Effort level approach (e.g., "none", "low", "medium", "high", "xhigh")
                modelParameters.reasoning_level = thinkingLevel;
            }
        }

        if (isEditMode && initialConfig) {
            const updateData: AIConfigUpdate = {
                name: finalName,
                model: model,
                api_key: (authType === "api_key" && apiKey) ? apiKey : undefined,
                api_url: apiUrl || defaultUrl || undefined,
                supports_text: true,
                supports_vision: supportsVision,
                supports_files: supportsFiles,
                model_parameters: modelParameters,
            };
            updateMutation.mutate({ id: initialConfig.id, data: updateData });
        } else {
            const createData: AIConfigCreate = {
                name: finalName,
                provider_type: providerType,
                auth_type: "api_key",
                model: model,
                api_key: (authType === "api_key" && apiKey) ? apiKey : undefined,
                api_url: apiUrl || defaultUrl || undefined,
                supports_text: true,
                supports_vision: supportsVision,
                supports_files: supportsFiles,
                model_parameters: modelParameters,
            };
            createMutation.mutate(createData);
        }
    };

    const needsApiUrl = providerType === "litellm" || providerType === "custom";
    const needsApiKey = true; // Always need API key now

    const isLoading = createMutation.isPending || updateMutation.isPending;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>{isEditMode ? "Edit AI Provider" : "Add AI Provider"}</DialogTitle>
                    <DialogDescription>
                        {isEditMode ? "Modify existing AI provider configuration." : "Configure a new AI provider for data extraction."}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <ProviderDropdown
                        value={providerType}
                        onChange={handleProviderChange}
                        currentInfo={{ name: providerInfo.name, icon_svg: providerInfo.icon_svg, icon_emoji: providerInfo.icon_emoji }}
                    />

                    {/* Provider Description */}
                    <p className="text-sm text-muted-foreground">
                        {providerInfo.description || ""}
                    </p>

                    {/* Name */}
                    <div className="space-y-2">
                        <Label>Display Name</Label>
                        <Input
                            placeholder={isEditMode ? name : generateAutoName()}
                            value={name}
                            onChange={handleNameChange}
                            onBlur={handleNameBlur}
                        />
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

                    {/* API Key */}
                    {needsApiKey && (
                        <div className="space-y-2">
                            <Label className="flex items-center gap-2">
                                <Key className="h-3.5 w-3.5" />
                                {isEditMode ? "New API Key (Leave empty to keep existing)" : "API Key"}
                            </Label>
                            <Input
                                type="password"
                                placeholder={providerType === "google" ? "AIza..." : "sk-..."}
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                            />
                        </div>
                    )}

                    <ModelAutocomplete
                        value={model}
                        onChange={(newModel) => {
                            setModel(newModel);
                            if (!isEditMode) setNameManuallyEdited(false);
                        }}
                        models={models}
                        requireVision={supportsVision}
                        requireFiles={supportsFiles}
                        providerType={providerType}
                        onCapabilitiesChange={(vision, files, thinking) => {
                            setSupportsVision(vision);
                            setSupportsFiles(files);
                            setThinkingCapability(thinking || null);

                            // Auto-enable if model supports thinking and user hasn't explicitly disabled (logic could be complex, simple for now)
                            // Or just set default params based on capability
                            if (thinking) {
                                if (thinking.method === "budget") {
                                    setThinkingBudget(thinking.min || 1024);
                                }
                            }
                        }}
                    />

                    {/* Thinking Configuration - Only shown for providers with reasoning support */}
                    {reasoningOptions && (
                        <div className="space-y-3 pt-2 border-t">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Brain className="h-4 w-4 text-primary" />
                                    <Label htmlFor="enable-thinking" className="cursor-pointer">Thinking (CoT)</Label>
                                    {thinkingCapability && (
                                        <Badge variant="secondary" className="text-[10px] h-5 px-1.5">
                                            Native
                                        </Badge>
                                    )}
                                </div>
                                <Switch
                                    id="enable-thinking"
                                    checked={thinkingEnabled}
                                    disabled={thinkingCapability?.can_disable === false}
                                    onCheckedChange={(checked) => {
                                        if (thinkingCapability?.can_disable === false && !checked) return;
                                        setThinkingEnabled(checked);
                                        // If enabling and no native capability, default to manual budget
                                        if (checked && !thinkingCapability && manualThinkingMethod === "none") {
                                            setManualThinkingMethod("budget");
                                        }
                                        // If disabling, we don't necessarily need to reset manual method, keeps state for re-enable
                                    }}
                                />
                            </div>

                            {thinkingEnabled && (
                                <div className="p-4 bg-muted/40 border rounded-md space-y-4 animate-in fade-in slide-in-from-top-1">
                                    {/* Only show level selector when provider supports it */}
                                    {reasoningOptions?.method === "level" && reasoningOptions.levels && (
                                        <div className="space-y-2">
                                            <Label>Reasoning Effort</Label>
                                            <div className="relative">
                                                <select
                                                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                                                    value={thinkingLevel}
                                                    onChange={(e) => setThinkingLevel(e.target.value)}
                                                >
                                                    {reasoningOptions.levels.map((level: string) => (
                                                        <option key={level} value={level}>
                                                            {level.charAt(0).toUpperCase() + level.slice(1)}
                                                        </option>
                                                    ))}
                                                </select>
                                                <ChevronDown className="absolute right-3 top-3 h-4 w-4 opacity-50 pointer-events-none" />
                                            </div>
                                            <p className="text-[11px] text-muted-foreground">
                                                Controls how much reasoning the model uses. Higher = more thorough but uses more tokens.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Test Result */}
                {testResult && (
                    <div className={`p-3 rounded-lg border ${testResult.success ? "border-green-500/30 bg-green-500/10" : "border-red-500/30 bg-red-500/10"}`}>
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
                        disabled={!model || isLoading}
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <Plus className="h-4 w-4 mr-2" />
                        )}
                        {isEditMode ? "Save Changes" : "Add Provider"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// --------------------------------------------------------------------------
// Updated AIConfigSection with Edit support
// --------------------------------------------------------------------------

export function AIConfigSection() {
    const queryClient = useQueryClient();
    const [showDialog, setShowDialog] = useState(false);
    const [editingConfig, setEditingConfig] = useState<AIProviderConfig | null>(null);
    const [testingId, setTestingId] = useState<number | null>(null);

    // Fetch AI configs
    const { data: configsResponse, isLoading } = useQuery({
        queryKey: ["admin", "ai-config"],
        queryFn: api.admin.getAIConfigs,
    });

    const configs = configsResponse?.data?.configs || [];

    const handleAdd = () => {
        setEditingConfig(null);
        setShowDialog(true);
    };

    const handleEdit = (config: AIProviderConfig) => {
        setEditingConfig(config);
        setShowDialog(true);
    };

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
                        <Button onClick={handleAdd}>
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
                                onEdit={() => handleEdit(config)}
                                onDelete={() => deleteMutation.mutate(config.id)}
                                onToggle={(enabled) =>
                                    toggleMutation.mutate({ id: config.id, enabled })
                                }
                            />
                        ))}
                        <Button
                            variant="outline"
                            className="w-full mt-4"
                            onClick={handleAdd}
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            Add Provider
                        </Button>
                    </div>
                )}
            </CardContent>

            {/* Provider Dialog (Create/Edit) */}
            <ProviderDialog
                open={showDialog}
                onOpenChange={setShowDialog}
                onSuccess={() => {
                    setShowDialog(false);
                    queryClient.invalidateQueries({ queryKey: ["admin", "ai-config"] });
                }}
                initialConfig={editingConfig}
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
    onEdit,
}: {
    config: AIProviderConfig;
    index: number;
    isTesting: boolean;
    onTest: () => void;
    onDelete: () => void;
    onToggle: (enabled: boolean) => void;
    onEdit: () => void;
}) {
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

            {/* Provider type icon */}
            {(() => {
                const pInfo = PROVIDER_INFO_MAP[config.provider_type] || FALLBACK_PROVIDER_INFO;
                return (
                    <div className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${pInfo.color}`} title={pInfo.name}>
                        <ProviderIcon iconSvg={pInfo.icon_svg} iconEmoji={pInfo.icon_emoji} className="h-6 w-6" />
                    </div>
                );
            })()}

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
                {/* Edit Button */}
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onEdit}
                    title="Edit"
                >
                    {/* SVG for Pencil since I can't easily import it without another edit */}
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-4 w-4"
                    >
                        <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                        <path d="m15 5 4 4" />
                    </svg>
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
