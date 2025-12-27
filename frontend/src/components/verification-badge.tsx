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
    const [flagReasonInput, setFlagReasonInput] = useState("");

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
            setFlagReasonInput("");
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

    // Build tooltip content
    const tooltipContent = () => {
        if (status === "verified" && verifiedAt) {
            return `Verified on ${formatDate(verifiedAt)}`;
        }
        if (status === "flagged" && flaggedAt) {
            return (
                <div className="space-y-1">
                    <div>Flagged on {formatDate(flaggedAt)}</div>
                    {flagReason && <div className="text-xs opacity-80">Reason: {flagReason}</div>}
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
            <Dialog open={flagDialogOpen} onOpenChange={setFlagDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Flag Data as Incorrect</DialogTitle>
                        <DialogDescription>
                            Please describe why this data appears to be incorrect. This helps
                            maintainers review and correct the issue.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <textarea
                            className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                            placeholder="Describe the issue... (minimum 10 characters)"
                            value={flagReasonInput}
                            onChange={(e) => setFlagReasonInput(e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                            {flagReasonInput.length}/500 characters
                        </p>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setFlagDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => flagMutation.mutate(flagReasonInput)}
                            disabled={flagReasonInput.length < 10 || flagReasonInput.length > 500 || flagMutation.isPending}
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
