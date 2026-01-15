/**
 * Overview View - DNO Detail Overview
 * 
 * Displays stats cards, source data accordion, and recent jobs preview.
 * Uses DNO context from parent for metadata, fetches lightweight summary data.
 */

import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Job } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Zap, Clock, Activity, CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { SourceDataAccordion } from "../components";
import type { DNODetailContext } from "./types";

function StatusIcon({ status, className }: { status: string; className?: string }) {
    switch (status) {
        case "completed":
            return <CheckCircle2 className={cn("h-4 w-4 text-green-500", className)} />;
        case "failed":
            return <XCircle className={cn("h-4 w-4 text-red-500", className)} />;
        case "running":
            return <Loader2 className={cn("h-4 w-4 text-blue-500 animate-spin", className)} />;
        default:
            return <AlertCircle className={cn("h-4 w-4 text-amber-500", className)} />;
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

    const { data: jobsResponse } = useQuery({
        queryKey: ["dno-jobs-preview", numericId],
        queryFn: () => api.dnos.getJobs(String(numericId), 5),
        enabled: !!numericId,
    });

    const netzentgelte = dataResponse?.data?.netzentgelte || [];
    const hlzf = dataResponse?.data?.hlzf || [];
    const jobs = jobsResponse?.data || [];

    // Calculate stats
    const netzentgelteCount = netzentgelte.filter((n: any) => n.leistung || n.arbeit).length;
    const hlzfCount = hlzf.filter((h: any) => h.winter || h.sommer).length;
    const years = new Set([...netzentgelte.map((n: any) => n.year), ...hlzf.map((h: any) => h.year)]).size;

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="p-4 flex flex-col justify-between">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
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
                        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-500">
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
                        <div className="p-2 rounded-lg bg-green-500/10 text-green-500">
                            <Activity className="h-5 w-5" />
                        </div>
                        <span className="text-sm text-muted-foreground font-medium">Status</span>
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className={cn(
                                "capitalize",
                                dno.status === 'crawled' ? 'bg-green-500/10 text-green-700 border-green-200' : 'bg-secondary'
                            )}>
                                {dno.status}
                            </Badge>
                            {dno.crawl_blocked_reason && (
                                <Badge variant="destructive" className="text-[10px]">
                                    Blocked
                                </Badge>
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2 truncate">
                            ID: {dno.slug}
                        </p>
                    </div>
                </Card>
            </div>

            {/* Source Info */}
            <Card className="p-1">
                <SourceDataAccordion
                    hasMastr={!!dno.has_mastr}
                    hasVnb={!!dno.has_vnb}
                    hasBdew={!!dno.has_bdew}
                    mastrData={dno.mastr_data}
                    vnbData={dno.vnb_data}
                    bdewData={dno.bdew_data}
                />
            </Card>

            {/* Recent Jobs Preview */}
            <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wider">Recent Jobs</h3>
                <Card className="divide-y">
                    {jobs.slice(0, 5).map((job: Job) => (
                        <div key={job.id} className="flex items-center justify-between p-3 text-sm">
                            <div className="flex items-center gap-3">
                                <StatusIcon status={job.status} />
                                <span className="font-medium">{job.data_type} {job.year}</span>
                            </div>
                            <span className="text-muted-foreground text-xs">
                                {new Date(job.created_at).toLocaleDateString()}
                            </span>
                        </div>
                    ))}
                    {jobs.length === 0 && (
                        <div className="p-4 text-center text-muted-foreground text-sm">No jobs recorded</div>
                    )}
                </Card>
            </div>
        </div>
    );
}
