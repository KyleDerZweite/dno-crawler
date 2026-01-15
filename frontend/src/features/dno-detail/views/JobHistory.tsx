/**
 * JobHistory View - Job List with Status
 * 
 * Fetches its own jobs data for lazy loading.
 */

import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Job } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DNODetailContext } from "./types";

function StatusIcon({ status, className }: { status: string; className?: string }) {
    switch (status) {
        case "completed":
            return <CheckCircle2 className={cn("h-5 w-5 text-green-500", className)} />;
        case "failed":
            return <XCircle className={cn("h-5 w-5 text-red-500", className)} />;
        case "running":
            return <Loader2 className={cn("h-5 w-5 text-blue-500 animate-spin", className)} />;
        default:
            return <AlertCircle className={cn("h-5 w-5 text-amber-500", className)} />;
    }
}

export function JobHistory() {
    const { numericId } = useOutletContext<DNODetailContext>();

    const { data: jobsResponse, isLoading } = useQuery({
        queryKey: ["dno-jobs", numericId],
        queryFn: () => api.dnos.getJobs(String(numericId), 50),
        enabled: !!numericId,
        refetchInterval: (query) => {
            const jobs = query.state.data?.data || [];
            const hasActive = jobs.some((j: Job) => ["pending", "running"].includes(j.status));
            return hasActive ? 3000 : false;
        },
    });

    const jobs = jobsResponse?.data || [];

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-4 animate-in fade-in duration-300">
            <h2 className="text-lg font-semibold">Job History</h2>
            <Card className="divide-y">
                {jobs.map((job: Job) => (
                    <div key={job.id} className="p-4 flex items-center justify-between hover:bg-muted/30">
                        <div className="flex items-center gap-4">
                            <StatusIcon status={job.status} />
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="font-medium">{job.job_type} job</span>
                                    <Badge variant="outline" className="text-xs">{job.year}</Badge>
                                    <Badge variant="outline" className="text-xs">{job.data_type}</Badge>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                                    <Clock className="h-3 w-3" />
                                    {new Date(job.created_at).toLocaleString()}
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            {job.status === "running" && (
                                <span className="text-sm text-muted-foreground">{job.progress}%</span>
                            )}
                            <Badge variant={
                                job.status === "completed" ? "default" :
                                    job.status === "failed" ? "destructive" :
                                        job.status === "running" ? "secondary" : "outline"
                            }>
                                {job.status}
                            </Badge>
                        </div>
                    </div>
                ))}
                {jobs.length === 0 && (
                    <div className="p-8 text-center text-muted-foreground">No jobs found</div>
                )}
            </Card>
        </div>
    );
}
