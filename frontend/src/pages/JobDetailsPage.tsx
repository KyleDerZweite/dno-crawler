import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import {
    ArrowLeft,
    Loader2,
    XCircle,
    Clock,
    CheckCircle,
    AlertCircle,
    Ban,
    PlayCircle,
} from "lucide-react";

import { api, type ApiResponse, type JobDetails } from "@/lib/api";
import { JOB_STATUS_CONFIG, type JobStatus } from "@/lib/job-status";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export function JobDetailsPage() {
    const { id } = useParams<{ id: string }>();
    const isValidId = id && /^\d+$/.test(id);
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { toast } = useToast();

    const { data, isLoading, error } = useQuery<ApiResponse<JobDetails>>({
        queryKey: ["job", id],
        queryFn: () => api.jobs.get(id!),
        enabled: Boolean(id && isValidId),
        refetchInterval: (query) => {
            // Poll every 3s while job is pending/running
            const job = query.state.data?.data;
            if (job?.status === "pending" || job?.status === "running") {
                return 3000;
            }
            return false;
        },
    });

    const deleteMutation = useMutation({
        mutationFn: () => api.jobs.delete(id!),
        onSuccess: () => {
            toast({ title: "Job deleted" });
            queryClient.invalidateQueries({ queryKey: ["jobs"] });
            // Also invalidate the DNO's job list cache
            const job = data?.data;
            if (job?.dno_id) {
                queryClient.invalidateQueries({ queryKey: ["dno-jobs", job.dno_id] });
            }
            navigate("/jobs");
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to delete", description: message });
        },
    });

    if (isLoading) {
        return (
            <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!isValidId || error || !data?.data) {
        return (
            <div className="space-y-4">
                <Button variant="ghost" onClick={() => navigate("/jobs")}>
                    <ArrowLeft className="mr-2 h-4 w-4" /> Back to Jobs
                </Button>
                <Card className="p-8 text-center">
                    <AlertCircle className="h-12 w-12 mx-auto text-red-500 mb-4" />
                    <h3 className="text-lg font-semibold mb-2">Job Not Found</h3>
                    <p className="text-muted-foreground">
                        The requested job could not be found.
                    </p>
                </Card>
            </div>
        );
    }

    const job = data.data;
    const status = job.status as JobStatus;
    const config = JOB_STATUS_CONFIG[status] ?? JOB_STATUS_CONFIG.pending;
    const StatusIcon = config.icon;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => navigate("/jobs")}>
                    <ArrowLeft className="h-5 w-5" />
                </Button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold text-foreground">
                        {job.dno_name || `Job ${job.id.slice(0, 8)}`}
                    </h1>
                    <p className="text-muted-foreground">
                        {job.year} · {job.data_type}
                    </p>
                </div>
                <Button
                    variant="destructive"
                    onClick={() => deleteMutation.mutate()}
                    disabled={deleteMutation.isPending}
                >
                    {deleteMutation.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                        <XCircle className="mr-2 h-4 w-4" />
                    )}
                    Delete
                </Button>
            </div>

            {/* Status Card */}
            <Card className="p-6">
                <div className="flex items-center gap-4">
                    <div className={cn("p-3 rounded-lg", config.color)}>
                        <StatusIcon className={cn("h-6 w-6", status === "running" && "animate-spin")} />
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-2">
                            <span className="font-semibold text-lg">{config.label}</span>
                            {job.progress > 0 && job.progress < 100 && (
                                <Badge variant="outline">{job.progress}%</Badge>
                            )}
                        </div>
                        <p className="text-muted-foreground">
                            {job.current_step || "Waiting to start..."}
                        </p>
                    </div>
                </div>

                {job.error_message && (
                    <div className="mt-4 p-4 bg-red-500/10 rounded-lg border border-red-500/20">
                        <p className="text-sm text-red-400">{job.error_message}</p>
                    </div>
                )}
            </Card>

            {/* Timeline */}
            <Card className="p-6">
                <h2 className="font-semibold mb-6">Timeline</h2>
                <div className="space-y-0 [&>div:last-child>div:first-child>div:last-child]:hidden">
                    {/* Lifecycle: Start */}
                    <div className="opacity-70">
                        <TimelineItem
                            icon={Clock}
                            label="Created"
                            time={job.created_at}
                            status="done"
                        />
                        {job.started_at && (
                            <TimelineItem
                                icon={PlayCircle}
                                label="Started"
                                time={job.started_at}
                                status="done"
                            />
                        )}
                    </div>

                    {/* Separator / Connector */}
                    {(job.steps?.length ?? 0) > 0 && (
                        <div className="flex gap-4 h-4">
                            <div className="flex flex-col items-center w-8">
                                <div className="w-px flex-1 border-l border-dashed border-border" />
                            </div>
                        </div>
                    )}

                    {/* Processing Steps */}
                    {job.steps && job.steps.length > 0 && (
                        <div className="relative pl-2 border-l-2 border-primary/10 ml-[15px] space-y-0 my-2 py-2 bg-muted/30 rounded-r-lg">
                            {job.steps.map((step, idx) => (
                                <TimelineItem
                                    key={step.id || idx}
                                    icon={step.status === "done" ? CheckCircle : step.status === "running" ? Loader2 : Clock}
                                    label={step.step_name || "Processing..."}
                                    time={step.completed_at || step.started_at}
                                    status={step.status}
                                    detail={(step.status === "done" ? (step.details?.result as string) : (step.details?.description as string)) || (step.details?.description as string)}
                                />
                            ))}
                        </div>
                    )}

                    {/* Separator / Connector */}
                    {job.completed_at && (
                        <div className="flex gap-4 h-4">
                            <div className="flex flex-col items-center w-8">
                                <div className="w-px flex-1 border-l border-dashed border-border" />
                            </div>
                        </div>
                    )}

                    {/* Lifecycle: End */}
                    {job.completed_at && (
                        <div className="mt-2">
                            <TimelineItem
                                icon={status === "completed" ? CheckCircle : status === "failed" ? AlertCircle : Ban}
                                label={status === "completed" ? "Completed" : status === "failed" ? "Failed" : "Cancelled"}
                                time={job.completed_at}
                                status="done"
                            />
                        </div>
                    )}
                </div>
            </Card>

            {/* Details */}
            <Card className="p-6">
                <h2 className="font-semibold mb-4">Details</h2>
                <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <dt className="text-muted-foreground">Job ID</dt>
                        <dd className="font-mono">{job.id}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">DNO</dt>
                        <dd>{job.dno_name || job.dno_id}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Year</dt>
                        <dd>{job.year}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Data Type</dt>
                        <dd>{job.data_type}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Triggered By</dt>
                        <dd>{job.triggered_by || "System"}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Priority</dt>
                        <dd>{job.priority}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Progress</dt>
                        <dd>{job.progress}%</dd>
                    </div>
                </dl>
            </Card>
        </div>
    );
}

function TimelineItem({
    icon: Icon,
    label,
    time,
    status,
    detail,
}: {
    icon: React.ElementType;
    label: string;
    time?: string;
    status: string;
    detail?: string;
}) {
    const isDone = status === "done";
    const isRunning = status === "running";

    return (
        <div className="flex gap-4 relative">
            {/* Icon column with dashed connector line */}
            <div className="flex flex-col items-center">
                <div className={cn(
                    "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center z-10",
                    isDone ? "bg-green-500/10 text-green-500" :
                        isRunning ? "bg-blue-500/10 text-blue-500" :
                            "bg-muted text-muted-foreground"
                )}>
                    <Icon className={cn("h-4 w-4", isRunning && "animate-spin")} />
                </div>
                {/* Dashed line connector - hidden for last item via CSS in parent */}
                <div className="w-px flex-1 border-l border-dashed border-border mt-1" />
            </div>
            {/* Content aligned with icon center */}
            <div className="flex-1 pb-4 pt-1">
                <div className="flex justify-between items-start">
                    <span className={isDone || isRunning ? "text-foreground" : "text-muted-foreground"}>
                        {label}
                    </span>
                    {time && (
                        <span className="text-xs text-muted-foreground">
                            {new Date(time).toLocaleString()}
                        </span>
                    )}
                </div>
                {detail && (
                    <p className="text-xs text-muted-foreground mt-1">{detail}</p>
                )}
            </div>
        </div>
    );
}

export default JobDetailsPage;
