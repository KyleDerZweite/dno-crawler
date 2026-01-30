/**
 * Overview View - DNO Detail Overview
 * 
 * Displays stats cards and source data section.
 * Uses DNO context from parent for metadata, fetches lightweight summary data.
 */

import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Netzentgelte, type HLZF } from "@/lib/api";
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

    const netzentgelte: Netzentgelte[] = dataResponse?.data?.netzentgelte || [];
    const hlzf: HLZF[] = dataResponse?.data?.hlzf || [];

    // Calculate stats
    const netzentgelteCount = netzentgelte.filter((n) => n.leistung || n.arbeit).length;
    const hlzfCount = hlzf.filter((h) => h.winter || h.sommer).length;
    // Calculate details
    const netzYears = Array.from(new Set(netzentgelte.map((n) => n.year))).sort((a, b) => b - a);
    const netzLevels = Array.from(new Set(netzentgelte.map((n) => n.voltage_level)));
    const hlzfYears = Array.from(new Set(hlzf.map((h) => h.year))).sort((a, b) => b - a);

    // Check which seasons are present in HLZF data
    const hlzfSeasons = new Set<string>();
    hlzf.forEach((h) => {
        if (h.winter) hlzfSeasons.add("Winter");
        if (h.fruehling) hlzfSeasons.add("Spring");
        if (h.sommer) hlzfSeasons.add("Summer");
        if (h.herbst) hlzfSeasons.add("Autumn");
    });

    // Get status display config
    const statusDisplay = getStatusDisplay(dno.status ?? "uncrawled", dno.crawl_blocked_reason);
    const StatusIcon = statusDisplay.icon;

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Netzentgelte Card */}
                <Card className="p-4 flex flex-col justify-between">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-500">
                            <Zap className="h-5 w-5" />
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">Netzentgelte</span>
                    </div>
                    <div>
                        <div className="flex items-baseline gap-2">
                            <p className="text-2xl font-bold">{netzentgelteCount}</p>
                            <span className="text-xs text-muted-foreground">records</span>
                        </div>

                        <div className="mt-4 pt-4 border-t border-border/50 space-y-2">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">Years found</span>
                                <span className="font-medium truncate max-w-[120px] text-right" title={netzYears.join(", ")}>
                                    {netzYears.slice(0, 3).join(", ")}{netzYears.length > 3 ? "..." : ""}
                                    {netzYears.length === 0 && "-"}
                                </span>
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">Voltage Levels</span>
                                <span className="font-medium truncate max-w-[120px] text-right" title={netzLevels.join(", ")}>
                                    {netzLevels.length > 0 ? `${netzLevels.length} levels` : "-"}
                                </span>
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">State</span>
                                <span className="font-medium text-purple-600">
                                    {netzentgelteCount > 0 ? "Active" : "No Data"}
                                </span>
                            </div>
                        </div>
                    </div>
                </Card>

                {/* HLZF Card */}
                <Card className="p-4 flex flex-col justify-between">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
                            <Clock className="h-5 w-5" />
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">HLZF</span>
                    </div>
                    <div>
                        <div className="flex items-baseline gap-2">
                            <p className="text-2xl font-bold">{hlzfCount}</p>
                            <span className="text-xs text-muted-foreground">windows</span>
                        </div>

                        <div className="mt-4 pt-4 border-t border-border/50 space-y-2">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">Years found</span>
                                <span className="font-medium truncate max-w-[120px] text-right" title={hlzfYears.join(", ")}>
                                    {hlzfYears.slice(0, 3).join(", ")}{hlzfYears.length > 3 ? "..." : ""}
                                    {hlzfYears.length === 0 && "-"}
                                </span>
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">Seasons</span>
                                <span className="font-medium truncate max-w-[120px] text-right">
                                    {hlzfSeasons.size > 0 ? `${hlzfSeasons.size}/4 found` : "-"}
                                </span>
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">State</span>
                                <span className="font-medium text-blue-600">
                                    {hlzfCount > 0 ? "Active" : "No Data"}
                                </span>
                            </div>
                        </div>
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

                        <div className="mt-4 pt-4 border-t border-border/50 space-y-2">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">Robots.txt</span>
                                {dno.robots_txt ? (
                                    <span className="text-green-600 font-medium">Found</span>
                                ) : (
                                    <span className="text-muted-foreground">Missing</span>
                                )}
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">Sitemap</span>
                                {dno.sitemap_urls && dno.sitemap_urls.length > 0 ? (
                                    <span className="text-green-600 font-medium">Found ({dno.sitemap_urls.length})</span>
                                ) : (
                                    <span className="text-muted-foreground">Missing</span>
                                )}
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">System</span>
                                <span className="font-medium truncate max-w-[100px] text-right" title={dno.cms_system || dno.tech_stack_details?.server}>
                                    {dno.cms_system || dno.tech_stack_details?.server || "-"}
                                </span>
                            </div>
                        </div>
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

