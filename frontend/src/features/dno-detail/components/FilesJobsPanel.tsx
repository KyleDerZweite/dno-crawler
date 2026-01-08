/**
 * FilesJobsPanel - Tabbed panel showing source files and recent jobs
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    FileDown,
    Calendar,
    Upload,
    Loader2,
    CheckCircle2,
    XCircle,
    AlertCircle,
    Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/api";

interface SourceFile {
    name: string;
    path: string;
    size: number;
}

interface FilesJobsPanelProps {
    files: SourceFile[];
    jobs: Job[];
    jobsLoading: boolean;
    onUploadClick: () => void;
}

function getStatusIcon(status: string) {
    switch (status) {
        case "completed":
            return <CheckCircle2 className="h-4 w-4 text-success" />;
        case "failed":
            return <XCircle className="h-4 w-4 text-destructive" />;
        case "running":
            return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
        case "pending":
            return <Clock className="h-4 w-4 text-muted-foreground" />;
        default:
            return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
}

function getStatusBadge(status: string) {
    const variants: Record<string, string> = {
        completed: "bg-success/10 text-success border-success/20",
        failed: "bg-destructive/10 text-destructive border-destructive/20",
        running: "bg-primary/10 text-primary border-primary/20",
        pending: "bg-muted text-muted-foreground border-muted",
        cancelled: "bg-muted text-muted-foreground border-muted",
    };
    return (
        <Badge
            variant="outline"
            className={cn("font-medium", variants[status] || variants.pending)}
        >
            {status}
        </Badge>
    );
}

export function FilesJobsPanel({
    files,
    jobs,
    jobsLoading,
    onUploadClick,
}: FilesJobsPanelProps) {
    const [activeTab, setActiveTab] = useState<"files" | "jobs">("files");

    return (
        <Card className="p-6">
            {/* Tab Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex gap-1 p-1 bg-muted rounded-lg">
                    <button
                        onClick={() => setActiveTab("files")}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all",
                            activeTab === "files"
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <FileDown className="h-4 w-4 text-orange-500" />
                        Source Files
                        {files.length > 0 && (
                            <Badge variant="secondary" className="ml-1 text-xs">
                                {files.length}
                            </Badge>
                        )}
                    </button>
                    <button
                        onClick={() => setActiveTab("jobs")}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all",
                            activeTab === "jobs"
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <Calendar className="h-4 w-4 text-green-500" />
                        Recent Jobs
                        {jobs.length > 0 && (
                            <Badge variant="secondary" className="ml-1 text-xs">
                                {jobs.length}
                            </Badge>
                        )}
                    </button>
                </div>
                {activeTab === "files" && (
                    <Button variant="outline" size="sm" onClick={onUploadClick}>
                        <Upload className="mr-2 h-4 w-4" />
                        Upload Files
                    </Button>
                )}
            </div>

            {/* Tab Content */}
            {activeTab === "files" ? (
                // Source Files Content
                files.length > 0 ? (
                    <div className="space-y-2">
                        {files.map((file, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="p-2 rounded bg-orange-500/10 text-orange-500">
                                        <FileDown className="h-4 w-4" />
                                    </div>
                                    <div>
                                        <p className="font-medium text-sm">{file.name}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {(file.size / 1024).toFixed(0)} KB
                                        </p>
                                    </div>
                                </div>
                                <Button variant="outline" size="sm" asChild>
                                    <a
                                        href={`${import.meta.env.VITE_API_URL}${file.path}`}
                                        download={file.name}
                                    >
                                        <FileDown className="mr-2 h-3 w-3" />
                                        Download
                                    </a>
                                </Button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">
                        No source files available
                    </p>
                )
            ) : // Recent Crawl Jobs Content
                jobsLoading ? (
                    <div className="flex justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : jobs.length > 0 ? (
                    <div className="space-y-2">
                        {jobs.map((job) => (
                            <div
                                key={job.id}
                                className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-muted/50 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    {getStatusIcon(job.status)}
                                    <div>
                                        <p className="font-medium flex items-center gap-2">
                                            {job.year} - {job.data_type}
                                            {job.job_type && job.job_type !== "full" && (
                                                <Badge variant="outline" className="text-xs">
                                                    {job.job_type === "crawl" ? "Crawl Only" : "Extract Only"}
                                                </Badge>
                                            )}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {new Date(job.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    {job.status === "running" && (
                                        <span className="text-sm text-muted-foreground">
                                            {job.progress}%
                                        </span>
                                    )}
                                    {getStatusBadge(job.status)}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">No crawl jobs yet</p>
                )}
        </Card>
    );
}
