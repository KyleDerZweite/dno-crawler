import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
    Loader2,
    CheckCircle2,
    XCircle,
    Circle,
    Clock,
    ArrowLeft,
    Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type BatchStatus, type BatchJobItem, type SearchStep } from "@/lib/api";

// Steps in the data extraction workflow
const WORKFLOW_STEPS = [
    "Finding PDF",
    "Searching Web",
    "Downloading PDF",
    "Validating PDF",
    "Extracting Data",
];

/**
 * BatchProgressPage: Display batch search progress with all jobs and their timelines
 * 
 * URL: /search/batch/:batchId
 */
export default function BatchProgressPage() {
    const { batchId } = useParams<{ batchId: string }>();
    const navigate = useNavigate();

    const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Polling for batch status
    useEffect(() => {
        if (!batchId) return;

        const fetchStatus = async () => {
            try {
                const status = await api.search.getBatchStatus(batchId);
                setBatchStatus(status);
                setIsLoading(false);

                // Stop polling if all jobs are done
                if (status.status === "completed" || status.status === "completed_with_errors") {
                    return true;
                }
                return false;
            } catch (err) {
                setError("Failed to load batch status");
                setIsLoading(false);
                return true;
            }
        };

        fetchStatus();

        const pollInterval = setInterval(async () => {
            const shouldStop = await fetchStatus();
            if (shouldStop) {
                clearInterval(pollInterval);
            }
        }, 1500);

        return () => clearInterval(pollInterval);
    }, [batchId]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error || !batchStatus) {
        return (
            <div className="space-y-8">
                <div>
                    <h1 className="text-3xl font-bold text-foreground">Batch Search</h1>
                    <p className="text-muted-foreground mt-2">Batch not found</p>
                </div>
                <Card className="p-6 border-destructive">
                    <div className="flex items-center gap-2 text-destructive">
                        <XCircle className="w-5 h-5" />
                        <p>{error || "This batch doesn't exist or you don't have access."}</p>
                    </div>
                    <Button
                        variant="outline"
                        className="mt-4"
                        onClick={() => navigate("/search")}
                    >
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back to Search
                    </Button>
                </Card>
            </div>
        );
    }

    const currentJob = batchStatus.jobs.find(j => j.status === "running");

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => navigate("/search")}
                >
                    <ArrowLeft className="w-5 h-5" />
                </Button>
                <div className="flex-1">
                    <h1 className="text-3xl font-bold text-foreground">Batch Search</h1>
                    <p className="text-muted-foreground mt-1">
                        {batchStatus.status === "running" ? "Processing..." :
                            batchStatus.status === "completed" ? "All jobs completed" :
                                batchStatus.status === "completed_with_errors" ? "Completed with some errors" :
                                    "Pending"}
                    </p>
                </div>
                <Badge
                    variant="outline"
                    className={`text-lg px-4 py-2 ${batchStatus.status === "completed" ? "border-green-500 text-green-500" :
                        batchStatus.status === "completed_with_errors" ? "border-yellow-500 text-yellow-500" :
                            batchStatus.status === "running" ? "border-primary text-primary" :
                                "border-muted text-muted-foreground"
                        }`}
                >
                    {batchStatus.completed + batchStatus.failed} / {batchStatus.total_jobs}
                </Badge>
            </div>

            {/* Overall Progress */}
            <Card className="p-6">
                <CardHeader className="p-0 pb-4">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Clock className="w-5 h-5" />
                        Overall Progress
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0 space-y-4">
                    <div className="w-full bg-muted rounded-full h-3">
                        <div
                            className="bg-primary h-3 rounded-full transition-all duration-300"
                            style={{ width: `${batchStatus.progress_percent}%` }}
                        />
                    </div>
                    <div className="flex justify-between text-sm text-muted-foreground">
                        <span>{batchStatus.completed} completed</span>
                        {batchStatus.failed > 0 && (
                            <span className="text-destructive">{batchStatus.failed} failed</span>
                        )}
                        <span>{batchStatus.pending} pending</span>
                    </div>
                </CardContent>
            </Card>

            {/* Current Job (if running) */}
            {currentJob && (
                <Card className="p-6 border-primary/30 bg-primary/5">
                    <CardHeader className="p-0 pb-4">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Play className="w-5 h-5 text-primary fill-primary" />
                            Current Job ({currentJob.batch_index}/{batchStatus.total_jobs})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="mb-4">
                            <p className="font-medium text-lg">{currentJob.input_text}</p>
                            <p className="text-sm text-muted-foreground">
                                {currentJob.current_step || "Starting..."}
                            </p>
                        </div>
                        <JobTimeline steps={currentJob.steps_history} />
                    </CardContent>
                </Card>
            )}

            {/* Job Queue */}
            <Card className="p-6">
                <CardHeader className="p-0 pb-4">
                    <CardTitle className="text-lg">All Jobs</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="space-y-2">
                        {batchStatus.jobs.map((job) => (
                            <JobRow
                                key={job.job_id}
                                job={job}
                                isCurrent={job.job_id === currentJob?.job_id}
                            />
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

/**
 * Single job row in the queue
 */
function JobRow({ job, isCurrent }: { job: BatchJobItem; isCurrent: boolean }) {
    const getStatusIcon = () => {
        switch (job.status) {
            case "running":
                return <Loader2 className="w-4 h-4 animate-spin text-primary" />;
            case "completed":
                return <CheckCircle2 className="w-4 h-4 text-green-500" />;
            case "failed":
                return <XCircle className="w-4 h-4 text-destructive" />;
            default:
                return <Circle className="w-4 h-4 text-muted-foreground/30" />;
        }
    };

    return (
        <div
            className={`flex items-center gap-4 p-3 rounded-lg transition-colors ${isCurrent ? "bg-primary/10 border border-primary/30" :
                job.status === "pending" ? "opacity-50" :
                    ""
                }`}
        >
            {getStatusIcon()}
            <div className="flex-1 min-w-0">
                <p className={`font-medium truncate ${job.status === "failed" ? "text-destructive" : ""
                    }`}>
                    {job.input_text}
                </p>
                {job.error ? (
                    <p className="text-sm text-destructive truncate">{job.error}</p>
                ) : job.current_step ? (
                    <p className="text-sm text-muted-foreground truncate">{job.current_step}</p>
                ) : null}
            </div>
            <Badge
                variant="outline"
                className={`shrink-0 ${job.status === "completed" ? "border-green-500/50 text-green-500" :
                    job.status === "running" ? "border-primary/50 text-primary" :
                        job.status === "failed" ? "border-destructive/50 text-destructive" :
                            "border-muted-foreground/30 text-muted-foreground/50"
                    }`}
            >
                {job.batch_index}/{job.batch_total}
            </Badge>
        </div>
    );
}

/**
 * Simple timeline for job steps
 */
function JobTimeline({ steps }: { steps: SearchStep[] }) {
    // Build merged steps: WORKFLOW_STEPS with backend status
    const stepsMap = new Map<string, SearchStep>();
    for (const step of steps) {
        stepsMap.set(step.label, step);
    }

    return (
        <div className="flex gap-2 flex-wrap">
            {WORKFLOW_STEPS.map((stepName) => {
                const step = stepsMap.get(stepName);
                const status = step?.status || "pending";

                return (
                    <Badge
                        key={stepName}
                        variant="outline"
                        className={`${status === "done" ? "border-green-500/50 text-green-500 bg-green-500/10" :
                            status === "running" ? "border-primary/50 text-primary bg-primary/10" :
                                status === "failed" ? "border-destructive/50 text-destructive bg-destructive/10" :
                                    "border-muted-foreground/20 text-muted-foreground/50"
                            }`}
                    >
                        {status === "running" && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                        {status === "done" && <CheckCircle2 className="w-3 h-3 mr-1" />}
                        {status === "failed" && <XCircle className="w-3 h-3 mr-1" />}
                        {stepName}
                    </Badge>
                );
            })}
        </div>
    );
}
