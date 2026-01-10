import { useState, useRef, useEffect } from "react";
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

// Model autocomplete component with fuzzy search
function ModelAutocomplete({
    value,
    onChange,
    models,
    requireVision,
    requireFiles,
    onCapabilitiesChange,
}: {
    value: string;
    onChange: (value: string) => void;
    models: AIModel[];
    requireVision?: boolean;
    requireFiles?: boolean;
    onCapabilitiesChange?: (vision: boolean, files: boolean) => void;
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState(value);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

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

    // Pre-filter models by required capabilities
    const capabilityFilteredModels = models.filter(m => {
        if (requireVision && !m.supports_vision) return false;
        if (requireFiles && !m.supports_files) return false;
        return true;
    });

    // Then apply fuzzy search filter
    const filteredModels = inputValue.length > 0
        ? capabilityFilteredModels.filter(m => fuzzyMatch(inputValue, m.id) || fuzzyMatch(inputValue, m.name))
        : capabilityFilteredModels;

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setInputValue(newValue);
        onChange(newValue);
        setIsOpen(true);
    };

    const handleSelect = (model: AIModel) => {
        setInputValue(model.id);
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

    const showDropdown = isOpen && filteredModels.length > 0;

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
                    placeholder={models.length > 0 ? "Search or enter model ID..." : "Enter model ID..."}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                />

                {/* Dropdown indicator */}
                {models.length > 0 && (
                    <button
                        type="button"
                        onClick={() => setIsOpen(!isOpen)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-accent rounded transition-colors"
                    >
                        <ChevronDown className={`h-4 w-4 opacity-50 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                    </button>
                )}

                {/* Dropdown Menu */}
                {showDropdown && (
                    <div className="absolute top-full left-0 right-0 z-[9999] mt-1 bg-popover border rounded-md shadow-lg max-h-48 overflow-y-auto">
                        {filteredModels.map((model) => {
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
                    </div>
                )}
            </div>
            {inputValue && filteredModels.length === 0 && models.length > 0 && (
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
    const [apiKey, setApiKey] = useState("");
    const [apiUrl, setApiUrl] = useState("");
    const [model, setModel] = useState("");
    const [supportsVision, setSupportsVision] = useState(true);
    const [supportsFiles, setSupportsFiles] = useState(false);
    const [authType, setAuthType] = useState<"api_key" | "cli">("api_key");
    const [useCliCreds, setUseCliCreds] = useState(false);

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

    // When provider changes, check for CLI creds
    const handleProviderChange = (v: string) => {
        const provider = v as AIProviderType;
        setProviderType(provider);
        setModel("");

        // Auto-select CLI auth for Google if creds available
        if (provider === "google" && detectedCreds.google?.available) {
            setAuthType("cli");
            setUseCliCreds(true);
            setName(`Google (${detectedCreds.google.email || "OAuth"})`);
        } else {
            setAuthType("api_key");
            setUseCliCreds(false);
        }
    };

    // Create mutation
    const createMutation = useMutation({
        mutationFn: (config: AIConfigCreate) => api.admin.createAIConfig(config),
        onSuccess: () => {
            onSuccess();
            // Reset form
            setName("");
            setApiKey("");
            setApiUrl("");
            setModel("");
            setAuthType("api_key");
            setUseCliCreds(false);
        },
    });

    const handleSubmit = () => {
        if (!name || !model) return;

        createMutation.mutate({
            name,
            provider_type: providerType,
            auth_type: authType,
            model: model,
            api_key: authType === "api_key" ? apiKey : undefined,
            api_url: apiUrl || defaultUrl || undefined,
            supports_text: true,
            supports_vision: supportsVision,
            supports_files: supportsFiles,
        });
    };

    const needsApiUrl = providerType === "litellm" || providerType === "custom";
    const needsApiKey = authType === "api_key" && !useCliCreds;

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

                    {/* CLI Credentials Detected Alert */}
                    {providerType === "google" && googleCredAvailable && (
                        <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                            <div className="flex items-center gap-2 text-green-500 font-medium mb-1">
                                <CheckCircle2 className="h-4 w-4" />
                                Gemini CLI credentials found!
                            </div>
                            <p className="text-sm text-muted-foreground">
                                Using account: <span className="font-medium text-foreground">{googleCredEmail}</span>
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                                No API key needed - uses your Google account's Gemini quota.
                            </p>
                        </div>
                    )}

                    {/* Name */}
                    <div className="space-y-2">
                        <Label>Display Name</Label>
                        <Input
                            placeholder="e.g., My OpenRouter Key"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
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

                    {/* API Key - only shown when not using CLI credentials */}
                    {needsApiKey && (
                        <div className="space-y-2">
                            <Label className="flex items-center gap-2">
                                <Key className="h-3.5 w-3.5" />
                                API Key
                            </Label>
                            <Input
                                type="password"
                                placeholder="sk-..."
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                            />
                        </div>
                    )}

                    {/* Model Selection */}
                    <ModelAutocomplete
                        value={model}
                        onChange={setModel}
                        models={models}
                        requireVision={supportsVision}
                        requireFiles={supportsFiles}
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

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!name || !model || createMutation.isPending}
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
