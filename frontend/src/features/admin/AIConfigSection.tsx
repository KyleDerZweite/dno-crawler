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
import { Checkbox } from "@/components/ui/checkbox";
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

// Provider display info
const PROVIDER_INFO: Record<AIProviderType, { name: string; color: string; logoUrl: string; description: string }> = {
    openrouter: {
        name: "OpenRouter",
        color: "bg-purple-500/20 text-purple-500",
        logoUrl: "https://models.dev/logos/openrouter.svg",
        description: "Recommended - Access 100+ models with unified API"
    },
    litellm: {
        name: "LiteLLM Proxy",
        color: "bg-cyan-500/20 text-cyan-500",
        logoUrl: "https://models.dev/logos/litellm.svg",
        description: "Coming Soon - Connect to your LiteLLM proxy"
    },
    custom: {
        name: "Custom API",
        color: "bg-gray-500/20 text-gray-400",
        logoUrl: "",
        description: "Any OpenAI-compatible endpoint (Ollama, vLLM, etc.)"
    },
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
    { value: "litellm", label: "LiteLLM Proxy" },
    { value: "custom", label: "Custom API" },
];

// Custom dropdown component styled like the VNB autocomplete
function ProviderDropdown({
    value,
    onChange,
}: {
    value: AIProviderType;
    onChange: (value: string) => void;
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
                                    {option.value === "litellm" && (
                                        <span className="text-xs text-muted-foreground">Coming Soon</span>
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

// Custom Number Input with Up/Down arrows
function NumberInput({
    value,
    onChange,
    min = 0,
    max,
    step = 1,
    disabled = false,
    className = "",
}: {
    value: number;
    onChange: (val: number) => void;
    min?: number;
    max?: number;
    step?: number;
    disabled?: boolean;
    className?: string;
}) {
    const handleIncrement = () => {
        if (disabled) return;
        const newValue = value + step;
        if (max !== undefined && newValue > max) return;
        onChange(newValue);
    };

    const handleDecrement = () => {
        if (disabled) return;
        const newValue = value - step;
        if (min !== undefined && newValue < min) return;
        onChange(newValue);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseInt(e.target.value);
        if (isNaN(val)) return;
        onChange(val);
    };

    return (
        <div className={`relative flex items-center ${className}`}>
            <Input
                type="number"
                value={value}
                onChange={handleChange}
                min={min}
                max={max}
                disabled={disabled}
                className="pr-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <div className="absolute right-1 flex flex-col gap-0.5">
                <button
                    type="button"
                    onClick={handleIncrement}
                    disabled={disabled || (max !== undefined && value >= max)}
                    className="p-0.5 hover:bg-accent rounded text-muted-foreground hover:text-foreground disabled:opacity-30 h-4 flex items-center justify-center"
                >
                    <ChevronDown className="h-3 w-3 rotate-180" />
                </button>
                <button
                    type="button"
                    onClick={handleDecrement}
                    disabled={disabled || (min !== undefined && value <= min)}
                    className="p-0.5 hover:bg-accent rounded text-muted-foreground hover:text-foreground disabled:opacity-30 h-4 flex items-center justify-center"
                >
                    <ChevronDown className="h-3 w-3" />
                </button>
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
    const queryClient = useQueryClient();
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

            // Initialize Thinking Configuration
            const params = initialConfig.model_parameters || {};
            if (params.thinking_level) {
                setThinkingEnabled(true);
                setThinkingLevel(params.thinking_level);
                // If we don't have capability info yet, assume manual level or native level
                // We'll let the UI resolve based on capability later, but for state:
                if (!thinkingCapability) setManualThinkingMethod("level");
            } else if (params.thinking_budget) {
                setThinkingEnabled(true);
                setThinkingBudget(params.thinking_budget);
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
            setAuthType("api_key");
            setModel("");
            setApiUrl("");
            setApiKey("");
            setSupportsVision(true);
            setSupportsFiles(false);
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

    // Fetch models for selected provider
    const { data: modelsData } = useQuery({
        queryKey: ["admin", "ai-models", providerType],
        queryFn: () => api.admin.getAIModels(providerType),
        enabled: open,
    });

    const models = modelsData?.data?.models || [];
    const defaultUrl = modelsData?.data?.default_url || "";
    const defaultModel = modelsData?.data?.default_model || "";
    const reasoningOptions = modelsData?.data?.reasoning_options || null;

    // Auto-fill default model when provider changes (create mode only)
    useEffect(() => {
        if (!isEditMode && open && defaultModel && !model) {
            setModel(defaultModel);
        }
    }, [defaultModel, open, isEditMode, model]);

    // Generate auto name based on provider and model
    const generateAutoName = () => {
        const providerName = PROVIDER_INFO[providerType]?.name || providerType;
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

                if (effectiveMethod === "budget" && reasoningOptions.param_name_tokens) {
                    testModelParameters[reasoningOptions.param_name_tokens] = thinkingBudget;
                } else if (effectiveMethod === "level" && reasoningOptions.param_name_effort) {
                    testModelParameters[reasoningOptions.param_name_effort] = thinkingLevel;
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

        if (thinkingEnabled && reasoningOptions) {
            // Use parameter names from backend
            const effectiveMethod = manualThinkingMethod !== "none"
                ? manualThinkingMethod
                : (reasoningOptions.method === "budget" ? "budget" : "level");

            if (effectiveMethod === "budget" && reasoningOptions.param_name_tokens) {
                modelParameters[reasoningOptions.param_name_tokens] = thinkingBudget;
            } else if (effectiveMethod === "level" && reasoningOptions.param_name_effort) {
                modelParameters[reasoningOptions.param_name_effort] = thinkingLevel;
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
                    />

                    {/* Provider Description */}
                    <p className="text-sm text-muted-foreground">
                        {PROVIDER_INFO[providerType]?.description}
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

                    {/* Thinking Configuration */}
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

                                {/* Manual Config Toggle (Only if no native capability) */}
                                {!thinkingCapability && (
                                    <div className="flex flex-col gap-2 p-3 bg-amber-500/10 border border-amber-500/20 rounded-md">
                                        <div className="flex items-center gap-2 text-xs text-amber-600 font-medium">
                                            <AlertTriangle className="h-3.5 w-3.5" />
                                            Manual Configuration Required
                                        </div>
                                        <p className="text-[11px] text-muted-foreground">
                                            This model does not advertise native thinking support. You can manually force thinking parameters.
                                        </p>

                                        <div className="flex items-center gap-2 mt-1">
                                            <Label className="text-xs">Method:</Label>
                                            <div className="flex bg-background rounded-md border p-0.5">
                                                <button
                                                    type="button"
                                                    onClick={() => setManualThinkingMethod("budget")}
                                                    className={`px-3 py-1 text-xs rounded-sm transition-colors ${manualThinkingMethod === "budget" ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-accent text-muted-foreground"}`}
                                                >
                                                    Token Budget
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setManualThinkingMethod("level")}
                                                    className={`px-3 py-1 text-xs rounded-sm transition-colors ${manualThinkingMethod === "level" ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-accent text-muted-foreground"}`}
                                                >
                                                    Reasoning Level
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Token Budget Input */}
                                {(thinkingCapability?.method === "budget" || manualThinkingMethod === "budget") && (
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <Label>Token Budget</Label>
                                            <div className="flex items-center gap-2">
                                                <Label htmlFor="auto-budget" className="text-xs text-muted-foreground cursor-pointer">
                                                    Auto
                                                </Label>
                                                <Switch
                                                    id="auto-budget"
                                                    checked={thinkingBudget === -1}
                                                    onCheckedChange={(checked) => {
                                                        if (checked) {
                                                            setThinkingBudget(-1);
                                                        } else {
                                                            setThinkingBudget(thinkingCapability?.min || 1024);
                                                        }
                                                    }}
                                                />
                                            </div>
                                        </div>
                                        {thinkingBudget === -1 ? (
                                            <div className="flex items-center gap-2 p-3 rounded-md bg-primary/10 border border-primary/20">
                                                <Zap className="h-4 w-4 text-primary" />
                                                <span className="text-sm">Automatic — Model determines optimal budget</span>
                                            </div>
                                        ) : (
                                            <>
                                                <NumberInput
                                                    value={thinkingBudget}
                                                    onChange={setThinkingBudget}
                                                    min={thinkingCapability?.min || 1024}
                                                    max={thinkingCapability?.max || 64000}
                                                    step={1024}
                                                    className="w-full"
                                                />
                                                <div className="flex justify-between text-[11px] text-muted-foreground">
                                                    <span>Min: {thinkingCapability?.min || 1024}</span>
                                                    <span>Max: {thinkingCapability?.max || 64000}</span>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                )}

                                {/* Level Dropdown */}
                                {(thinkingCapability?.method === "level" || manualThinkingMethod === "level") && (
                                    <div className="space-y-2">
                                        <Label>Reasoning Effort</Label>
                                        <div className="relative">
                                            <select
                                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                                                value={thinkingLevel}
                                                onChange={(e) => setThinkingLevel(e.target.value)}
                                            >
                                                <option value="low">Low</option>
                                                <option value="medium">Medium</option>
                                                <option value="high">High</option>
                                            </select>
                                            <ChevronDown className="absolute right-3 top-3 h-4 w-4 opacity-50 pointer-events-none" />
                                        </div>
                                        <p className="text-[11px] text-muted-foreground">
                                            Controls the depth of reasoning.
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

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
    const info = PROVIDER_INFO[config.provider_type] || PROVIDER_INFO.custom;
    // ... import { Pencil } from "lucide-react" ... 
    // We need to add the import if it's missing, but I'll assume lucide-react has it. 
    // I can't add imports easily here, so I'll check if Pencil is imported.
    // If not, I'll add it to the import list in a separate step or just use a generic icon/text.
    // Actually, I can replace the whole import block if needed, but the current tool call targets the end of file.
    // I will assume I can add an Edit button.

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
