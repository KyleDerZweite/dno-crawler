/**
 * Overview View - DNO Detail Overview
 * 
 * Displays stats cards and source data section.
 * Uses DNO context from parent for metadata, fetches lightweight summary data.
 */

import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Zap, Clock, Activity, Shield, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { ExternalDataSources } from "../components";
import type { DNODetailContext } from "./types";

/**
 * Human-readable labels for blocked reasons
 */
const BLOCKED_REASON_LABELS: Record<string, string> = {
    cloudflare: "Cloudflare Protected",
    access_denied: "Access Denied",
    rate_limited_or_ip_blocked: "Rate Limited",
    authentication_required: "Auth Required",
    robots_disallow_all: "Blocked by robots.txt",
    timeout: "Timeout",
    connection_failed: "Connection Failed",
    javascript_required: "JS Required",
    javascript_challenge: "JS Challenge",
    check_failed: "Check Failed",
    request_error: "Request Error",
};

/**
 * Get display configuration for DNO status
 */
function getStatusDisplay(status: string, blockedReason?: string | null) {
    // For protected status, show the specific reason
    if (status === "protected" && blockedReason) {
        const label = BLOCKED_REASON_LABELS[blockedReason] || "Protected";
        return {
            label,
            variant: "outline" as const,
            className: "bg-orange-500/10 text-orange-500 border-orange-500 hover:bg-orange-500/15",
            icon: ShieldAlert,
        };
    }

    // Status-based display
    switch (status) {
        case "crawled":
            return {
                label: "Crawled",
                variant: "outline" as const,
                className: "bg-green-500/10 text-green-500 border-green-500 hover:bg-green-500/15",
                icon: Activity,
            };
        case "protected":
            return {
                label: "Protected",
                variant: "outline" as const,
                className: "bg-orange-500/10 text-orange-500 border-orange-500 hover:bg-orange-500/15",
                icon: Shield,
            };
        case "failed":
            return {
                label: "Failed",
                variant: "outline" as const,
                className: "bg-red-500/10 text-red-500 border-red-500 hover:bg-red-500/15",
                icon: ShieldAlert,
            };
        default:
            return {
                label: "Uncrawled",
                variant: "outline" as const,
                className: "bg-muted/50 text-muted-foreground border-muted-foreground/30 hover:bg-muted/70",
                icon: Activity,
            };
    }
}

export function Overview() {
    const { dno, numericId } = useOutletContext<DNODetailContext>();

    // Lightweight data for overview stats
    const { data: dataResponse } = useQuery({
        queryKey: ["dno-data-summary", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: !!numericId,
    });

    const netzentgelte = dataResponse?.data?.netzentgelte || [];
    const hlzf = dataResponse?.data?.hlzf || [];

    // Calculate stats
    const netzentgelteCount = netzentgelte.filter((n: any) => n.leistung || n.arbeit).length;
    const hlzfCount = hlzf.filter((h: any) => h.winter || h.sommer).length;
    const years = new Set([...netzentgelte.map((n: any) => n.year), ...hlzf.map((h: any) => h.year)]).size;

    // Get status display config
    const statusDisplay = getStatusDisplay(dno.status ?? "uncrawled", dno.crawl_blocked_reason);
    const StatusIcon = statusDisplay.icon;

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="p-4 flex flex-col justify-between">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-500">
                            <Zap className="h-5 w-5" />
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">Netzentgelte</span>
                    </div>
                    <div>
                        <p className="text-2xl font-bold">{netzentgelteCount}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Records found across {years} years
                        </p>
                    </div>
                </Card>
                <Card className="p-4 flex flex-col justify-between">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
                            <Clock className="h-5 w-5" />
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">HLZF</span>
                    </div>
                    <div>
                        <p className="text-2xl font-bold">{hlzfCount}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Time windows identified
                        </p>
                    </div>
                </Card>
                <Card className="p-4 flex flex-col justify-between bg-muted/30">
                    <div className="flex items-center gap-3 mb-2">
                        <div className={cn(
                            "p-2 rounded-lg",
                            (dno.status ?? "uncrawled") === "protected"
                                ? "bg-orange-500/10 text-orange-500"
                                : (dno.status ?? "uncrawled") === "crawled"
                                    ? "bg-green-500/10 text-green-500"
                                    : "bg-muted text-muted-foreground"
                        )}>
                            <StatusIcon className="h-5 w-5" />
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">Status</span>
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <Badge variant={statusDisplay.variant} className={statusDisplay.className}>
                                {statusDisplay.label}
                            </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2 truncate">
                            ID: {dno.slug}
                        </p>
                    </div>
                </Card>
            </div>

            {/* Source Info */}
            <Card>
                <ExternalDataSources
                    hasMastr={!!dno.has_mastr}
                    hasVnb={!!dno.has_vnb}
                    hasBdew={!!dno.has_bdew}
                    mastrData={dno.mastr_data}
                    vnbData={dno.vnb_data}
                    bdewData={dno.bdew_data}
                />
            </Card>
        </div>
    );
}

