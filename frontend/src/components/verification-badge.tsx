import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import {
    CheckCircle2,
    AlertTriangle,
    Circle,
    Flag,
    XCircle,
    Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AxiosError } from "axios";

interface VerificationBadgeProps {
    status: string;
    verifiedBy?: string;
    verifiedAt?: string;
    flaggedBy?: string;
    flaggedAt?: string;
    flagReason?: string;
    recordId: number;
    recordType: "netzentgelte" | "hlzf";
    dnoId: string;
    compact?: boolean;
}

/**
 * Verification status badge with interactive actions.
 * Shows status indicator and allows users to verify/flag/unflag data.
 */
export function VerificationBadge({
    status,
    verifiedBy,
    verifiedAt,
    flaggedBy,
    flaggedAt,
    flagReason,
    recordId,
    recordType,
    dnoId,
    compact = false,
}: VerificationBadgeProps) {
    const { isAuthenticated, canManageFlags } = useAuth();
    const { toast } = useToast();
    const queryClient = useQueryClient();

    const [flagDialogOpen, setFlagDialogOpen] = useState(false);
    const [flagNotes, setFlagNotes] = useState("");
    const [issueType, setIssueType] = useState<string>("");
    const [affectedFields, setAffectedFields] = useState<string[]>([]);

    // Field options based on record type
    const netzentgelteFields = [
        { id: "leistung_high", label: "Leistung (≥2.500 h/a)" },
        { id: "arbeit_high", label: "Arbeit (≥2.500 h/a)" },
        { id: "leistung_low", label: "Leistung (<2.500 h/a)" },
        { id: "arbeit_low", label: "Arbeit (<2.500 h/a)" },
    ];

    const hlzfFields = [
        { id: "winter", label: "Winter" },
        { id: "fruehling", label: "Frühling" },
        { id: "sommer", label: "Sommer" },
        { id: "herbst", label: "Herbst" },
    ];

    const issueTypes = [
        { id: "wrong_values", label: "Wrong values", desc: "Values don't match source" },
        { id: "mixed_up", label: "Values mixed up", desc: "Values are in wrong columns" },
        { id: "missing", label: "Missing data", desc: "Some values should be present" },
        { id: "other", label: "Other issue", desc: "Different problem" },
    ];

    const fields = recordType === "netzentgelte" ? netzentgelteFields : hlzfFields;

    // Build reason string from selections
    const buildFlagReason = (): string => {
        const parts: string[] = [];

        const issueLabel = issueTypes.find(t => t.id === issueType)?.label;
        if (issueLabel) parts.push(`Issue: ${issueLabel}`);

        if (affectedFields.length > 0) {
            const fieldLabels = affectedFields.map(
                f => fields.find(field => field.id === f)?.label
            ).filter(Boolean);
            parts.push(`Fields: ${fieldLabels.join(", ")}`);
        }

        if (flagNotes.trim()) {
            parts.push(`Notes: ${flagNotes.trim()}`);
        }

        return parts.join(" | ");
    };

    const canSubmitFlag = issueType !== "" && (issueType === "other" ? flagNotes.length >= 10 : true);

    const resetFlagDialog = () => {
        setFlagNotes("");
        setIssueType("");
        setAffectedFields([]);
    };

    const toggleField = (fieldId: string) => {
        setAffectedFields(prev =>
            prev.includes(fieldId)
                ? prev.filter(f => f !== fieldId)
                : [...prev, fieldId]
        );
    };



    // Mutations for verification actions
    const verifyMutation = useMutation({
        mutationFn: () =>
            recordType === "netzentgelte"
                ? api.verification.verifyNetzentgelte(recordId)
                : api.verification.verifyHLZF(recordId),
        onSuccess: () => {
            toast({ title: "Verified", description: "Record marked as verified" });
            queryClient.invalidateQueries({ queryKey: ["dno-data", dnoId] });
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Verification failed", description: message });
        },
    });

    const flagMutation = useMutation({
        mutationFn: (reason: string) =>
            recordType === "netzentgelte"
                ? api.verification.flagNetzentgelte(recordId, reason)
                : api.verification.flagHLZF(recordId, reason),
        onSuccess: () => {
            toast({ title: "Flagged", description: "Record flagged for review" });
            queryClient.invalidateQueries({ queryKey: ["dno-data", dnoId] });
            setFlagDialogOpen(false);
            resetFlagDialog();
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Flagging failed", description: message });
        },
    });

    const unflagMutation = useMutation({
        mutationFn: () =>
            recordType === "netzentgelte"
                ? api.verification.unflagNetzentgelte(recordId)
                : api.verification.unflagHLZF(recordId),
        onSuccess: () => {
            toast({ title: "Unflagged", description: "Flag removed from record" });
            queryClient.invalidateQueries({ queryKey: ["dno-data", dnoId] });
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Unflagging failed", description: message });
        },
    });

    const isPending = verifyMutation.isPending || flagMutation.isPending || unflagMutation.isPending;

    // Status icon and styling
    const getStatusDisplay = () => {
        switch (status) {
            case "verified":
                return {
                    icon: <CheckCircle2 className="h-4 w-4" />,
                    label: "Verified",
                    className: "text-green-600 bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800",
                };
            case "flagged":
                return {
                    icon: <AlertTriangle className="h-4 w-4" />,
                    label: "Flagged",
                    className: "text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800",
                };
            case "rejected":
                return {
                    icon: <XCircle className="h-4 w-4" />,
                    label: "Rejected",
                    className: "text-red-600 bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800",
                };
            default:
                return {
                    icon: <Circle className="h-4 w-4" />,
                    label: "Unverified",
                    className: "text-gray-500 bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-700",
                };
        }
    };

    const statusDisplay = getStatusDisplay();

    // Format date for tooltip
    const formatDate = (dateStr?: string) => {
        if (!dateStr) return "";
        return new Date(dateStr).toLocaleDateString("de-DE", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    // Parse structured flag reason for display
    const parseFlagReason = (reason?: string) => {
        if (!reason) return null;

        const parts: { issue?: string; fields?: string; notes?: string } = {};
        reason.split(" | ").forEach(part => {
            if (part.startsWith("Issue: ")) parts.issue = part.replace("Issue: ", "");
            else if (part.startsWith("Fields: ")) parts.fields = part.replace("Fields: ", "");
            else if (part.startsWith("Notes: ")) parts.notes = part.replace("Notes: ", "");
        });

        return parts;
    };

    // Build tooltip content
    const tooltipContent = () => {
        if (status === "verified" && verifiedAt) {
            return `Verified on ${formatDate(verifiedAt)}`;
        }
        if (status === "flagged") {
            const parsed = parseFlagReason(flagReason);
            return (
                <div className="space-y-1.5 max-w-xs">
                    <div className="font-medium text-amber-400">
                        ⚠ Flagged{flaggedAt ? ` on ${formatDate(flaggedAt)}` : ""}
                    </div>
                    {parsed?.issue && (
                        <div className="text-xs">
                            <span className="text-muted-foreground">Issue:</span>{" "}
                            <span className="font-medium">{parsed.issue}</span>
                        </div>
                    )}
                    {parsed?.fields && (
                        <div className="text-xs">
                            <span className="text-muted-foreground">Fields:</span>{" "}
                            <span>{parsed.fields}</span>
                        </div>
                    )}
                    {parsed?.notes && (
                        <div className="text-xs">
                            <span className="text-muted-foreground">Notes:</span>{" "}
                            <span className="italic">{parsed.notes}</span>
                        </div>
                    )}
                    {!parsed?.issue && flagReason && (
                        <div className="text-xs opacity-80">{flagReason}</div>
                    )}
                    {!parsed?.issue && !flagReason && (
                        <div className="text-xs opacity-80">No details provided</div>
                    )}
                </div>
            );
        }
        return "Not yet verified";
    };

    if (!isAuthenticated) {
        // Read-only view for unauthenticated users
        return (
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Badge
                            variant="outline"
                            className={cn("gap-1 font-normal cursor-default", statusDisplay.className)}
                        >
                            {statusDisplay.icon}
                            {!compact && statusDisplay.label}
                        </Badge>
                    </TooltipTrigger>
                    <TooltipContent>{tooltipContent()}</TooltipContent>
                </Tooltip>
            </TooltipProvider>
        );
    }

    return (
        <>
            <TooltipProvider>
                <div className="flex items-center gap-1">
                    {/* Status Badge */}
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Badge
                                variant="outline"
                                className={cn("gap-1 font-normal cursor-default", statusDisplay.className)}
                            >
                                {statusDisplay.icon}
                                {!compact && statusDisplay.label}
                            </Badge>
                        </TooltipTrigger>
                        <TooltipContent>{tooltipContent()}</TooltipContent>
                    </Tooltip>

                    {/* Action Buttons */}
                    {status !== "verified" && status !== "flagged" && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                                    onClick={() => verifyMutation.mutate()}
                                    disabled={isPending}
                                >
                                    {verifyMutation.isPending ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                    )}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Mark as verified</TooltipContent>
                        </Tooltip>
                    )}

                    {status !== "flagged" && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0 text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                                    onClick={() => setFlagDialogOpen(true)}
                                    disabled={isPending}
                                >
                                    <Flag className="h-3.5 w-3.5" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Flag as incorrect</TooltipContent>
                        </Tooltip>
                    )}

                    {status === "flagged" && canManageFlags() && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0 text-gray-600 hover:text-gray-700 hover:bg-gray-50"
                                    onClick={() => unflagMutation.mutate()}
                                    disabled={isPending}
                                >
                                    {unflagMutation.isPending ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <XCircle className="h-3.5 w-3.5" />
                                    )}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Remove flag</TooltipContent>
                        </Tooltip>
                    )}
                </div>
            </TooltipProvider>

            {/* Flag Dialog */}
            <Dialog open={flagDialogOpen} onOpenChange={(open) => {
                setFlagDialogOpen(open);
                if (!open) resetFlagDialog();
            }}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Flag Data as Incorrect</DialogTitle>
                        <DialogDescription>
                            Select the type of issue and which fields are affected.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-5 py-4">
                        {/* Issue Type Selection */}
                        <div className="space-y-3">
                            <label className="text-sm font-medium">What's the issue?</label>
                            <div className="grid grid-cols-2 gap-2">
                                {issueTypes.map((type) => (
                                    <button
                                        key={type.id}
                                        type="button"
                                        onClick={() => setIssueType(type.id)}
                                        className={cn(
                                            "flex flex-col items-start p-3 rounded-lg border text-left transition-all",
                                            issueType === type.id
                                                ? "border-primary bg-primary/5 ring-1 ring-primary"
                                                : "border-border hover:border-primary/50 hover:bg-muted/50"
                                        )}
                                    >
                                        <span className="text-sm font-medium">{type.label}</span>
                                        <span className="text-xs text-muted-foreground">{type.desc}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Affected Fields Selection */}
                        <div className="space-y-3">
                            <label className="text-sm font-medium">
                                Which fields are affected? <span className="text-muted-foreground font-normal">(optional)</span>
                            </label>
                            <div className={cn(
                                "grid gap-2",
                                recordType === "netzentgelte" ? "grid-cols-2" : "grid-cols-4"
                            )}>
                                {fields.map((field) => (
                                    <button
                                        key={field.id}
                                        type="button"
                                        onClick={() => toggleField(field.id)}
                                        className={cn(
                                            "flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-all",
                                            affectedFields.includes(field.id)
                                                ? "border-amber-500 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                                                : "border-border hover:border-amber-500/50 hover:bg-muted/50"
                                        )}
                                    >
                                        <div className={cn(
                                            "w-4 h-4 rounded border-2 flex items-center justify-center transition-colors",
                                            affectedFields.includes(field.id)
                                                ? "border-amber-500 bg-amber-500"
                                                : "border-muted-foreground/50"
                                        )}>
                                            {affectedFields.includes(field.id) && (
                                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                                </svg>
                                            )}
                                        </div>
                                        {field.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Additional Notes */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium">
                                Additional notes {issueType === "other" && <span className="text-destructive">*</span>}
                            </label>
                            <textarea
                                className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                                placeholder={issueType === "other" ? "Please describe the issue... (minimum 10 characters)" : "Optional additional details..."}
                                value={flagNotes}
                                onChange={(e) => setFlagNotes(e.target.value)}
                            />
                            {issueType === "other" && flagNotes.length > 0 && flagNotes.length < 10 && (
                                <p className="text-xs text-destructive">Minimum 10 characters required</p>
                            )}
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setFlagDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => flagMutation.mutate(buildFlagReason())}
                            disabled={!canSubmitFlag || flagMutation.isPending}
                        >
                            {flagMutation.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Flagging...
                                </>
                            ) : (
                                <>
                                    <Flag className="mr-2 h-4 w-4" />
                                    Flag Data
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
