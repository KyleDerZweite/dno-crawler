import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type APIKeyInfo, type APIKeyCreateResponse } from "@/lib/api";
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
    Key,
    Plus,
    Trash2,
    Loader2,
    Copy,
    Check,
    AlertTriangle,
} from "lucide-react";

const AVAILABLE_ROLES = ["ADMIN", "MEMBER", "MAINTAINER"] as const;

function formatRelativeTime(dateStr: string | null): string {
    if (!dateStr) return "Never";
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return date.toLocaleDateString("de-DE");
}

export function APIKeysSection() {
    const queryClient = useQueryClient();
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [createdKey, setCreatedKey] = useState<APIKeyCreateResponse | null>(null);

    const { data: keysResponse, isLoading } = useQuery({
        queryKey: ["admin", "api-keys"],
        queryFn: api.admin.getAPIKeys,
    });

    const keys = keysResponse?.keys || [];

    const deleteMutation = useMutation({
        mutationFn: (id: number) => api.admin.deleteAPIKey(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin", "api-keys"] });
        },
    });

    return (
        <>
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Key className="h-5 w-5 text-primary" />
                        API Keys
                        {keys.length > 0 && (
                            <Badge variant="secondary" className="ml-2">
                                {keys.length}
                            </Badge>
                        )}
                    </CardTitle>
                    <CardDescription>
                        Manage machine API keys for scripts and integrations.
                        Keys authenticate via Bearer token with a <code>dno_</code> prefix.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div className="flex items-center justify-center py-8 text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin mr-2" />
                            Loading API keys...
                        </div>
                    ) : keys.length === 0 ? (
                        <div className="text-center py-8 border border-dashed border-border rounded-lg">
                            <Key className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                            <p className="text-muted-foreground mb-4">
                                No API keys created. Create a key to enable script access.
                            </p>
                            <Button onClick={() => setShowCreateDialog(true)}>
                                <Plus className="h-4 w-4 mr-2" />
                                Create API Key
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {keys.map((key) => (
                                <APIKeyCard
                                    key={key.id}
                                    apiKey={key}
                                    onDelete={() => deleteMutation.mutate(key.id)}
                                    isDeleting={deleteMutation.isPending}
                                />
                            ))}
                            <Button
                                variant="outline"
                                className="w-full mt-4"
                                onClick={() => setShowCreateDialog(true)}
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Create API Key
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Create Dialog */}
            <CreateAPIKeyDialog
                open={showCreateDialog}
                onOpenChange={setShowCreateDialog}
                onCreated={(response) => {
                    setShowCreateDialog(false);
                    setCreatedKey(response);
                    queryClient.invalidateQueries({ queryKey: ["admin", "api-keys"] });
                }}
            />

            {/* Key Created Dialog (show plaintext key once) */}
            <KeyCreatedDialog
                open={createdKey !== null}
                onOpenChange={() => setCreatedKey(null)}
                keyData={createdKey}
            />
        </>
    );
}

function APIKeyCard({
    apiKey,
    onDelete,
    isDeleting,
}: {
    apiKey: APIKeyInfo;
    onDelete: () => void;
    isDeleting: boolean;
}) {
    return (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card">
            <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-primary/10">
                <Key className="h-5 w-5 text-primary" />
            </div>

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{apiKey.name}</span>
                    {apiKey.roles.map((role) => (
                        <Badge key={role} variant="secondary" className="text-[10px] h-5 px-1.5">
                            {role}
                        </Badge>
                    ))}
                </div>
                <div className="text-xs text-muted-foreground flex items-center gap-2">
                    <code className="bg-muted px-1 rounded">{apiKey.key_prefix}...</code>
                    <span className="text-muted-foreground/50">|</span>
                    <span>{apiKey.request_count.toLocaleString()} requests</span>
                    <span className="text-muted-foreground/50">|</span>
                    <span>Last used: {formatRelativeTime(apiKey.last_used_at)}</span>
                </div>
            </div>

            <Button
                variant="ghost"
                size="sm"
                onClick={onDelete}
                disabled={isDeleting}
                className="text-destructive hover:text-destructive"
                title="Delete API key"
            >
                <Trash2 className="h-4 w-4" />
            </Button>
        </div>
    );
}

function CreateAPIKeyDialog({
    open,
    onOpenChange,
    onCreated,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: (response: APIKeyCreateResponse) => void;
}) {
    const [name, setName] = useState("");
    const [selectedRoles, setSelectedRoles] = useState<string[]>(["MEMBER"]);

    const createMutation = useMutation({
        mutationFn: () => api.admin.createAPIKey({ name, roles: selectedRoles }),
        onSuccess: (response) => {
            onCreated(response);
            setName("");
            setSelectedRoles(["MEMBER"]);
        },
    });

    const toggleRole = (role: string) => {
        setSelectedRoles((prev) =>
            prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
        );
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Create API Key</DialogTitle>
                    <DialogDescription>
                        Create a new API key for machine access. The key will only be shown once.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label>Name</Label>
                        <Input
                            placeholder="e.g., bulk-enqueue-script"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Roles</Label>
                        <div className="flex gap-4">
                            {AVAILABLE_ROLES.map((role) => (
                                <label key={role} className="flex items-center gap-2 text-sm">
                                    <Checkbox
                                        checked={selectedRoles.includes(role)}
                                        onCheckedChange={() => toggleRole(role)}
                                    />
                                    {role}
                                </label>
                            ))}
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={() => createMutation.mutate()}
                        disabled={!name.trim() || selectedRoles.length === 0 || createMutation.isPending}
                    >
                        {createMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <Plus className="h-4 w-4 mr-2" />
                        )}
                        Create Key
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function KeyCreatedDialog({
    open,
    onOpenChange,
    keyData,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    keyData: APIKeyCreateResponse | null;
}) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        if (!keyData) return;
        await navigator.clipboard.writeText(keyData.key);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Key className="h-5 w-5 text-primary" />
                        API Key Created
                    </DialogTitle>
                    <DialogDescription>
                        Copy this key now. It will not be shown again.
                    </DialogDescription>
                </DialogHeader>

                {keyData && (
                    <div className="space-y-4 py-4">
                        <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/5">
                            <div className="flex items-start gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                                <p className="text-sm text-amber-600">
                                    Store this key securely. You will not be able to see it again after closing this dialog.
                                </p>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>API Key</Label>
                            <div className="flex gap-2">
                                <code className="flex-1 p-2 rounded-md border bg-muted text-sm font-mono break-all select-all">
                                    {keyData.key}
                                </code>
                                <Button variant="outline" size="sm" onClick={handleCopy}>
                                    {copied ? (
                                        <Check className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <Copy className="h-4 w-4" />
                                    )}
                                </Button>
                            </div>
                        </div>

                        <div className="text-sm text-muted-foreground">
                            <p><strong>Name:</strong> {keyData.name}</p>
                            <p><strong>Roles:</strong> {keyData.roles.join(", ")}</p>
                        </div>

                        <div className="p-3 rounded-lg bg-muted/50 text-sm">
                            <p className="font-medium mb-1">Usage</p>
                            <code className="text-xs">
                                curl -H "Authorization: Bearer {keyData.key_prefix}..." ...
                            </code>
                        </div>
                    </div>
                )}

                <DialogFooter>
                    <Button onClick={() => onOpenChange(false)}>
                        Done
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
