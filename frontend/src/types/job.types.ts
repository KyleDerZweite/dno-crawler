/**
 * Job and task types for crawl/extraction operations.
 */

// Job status type
export type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

// Job type (what kind of processing)
export type JobType = "full" | "crawl" | "extract";

// Base job information
export interface Job {
    id: string;
    dno_id: string;
    dno_name?: string;
    year: number;
    data_type: string;
    job_type?: JobType;
    status: JobStatus;
    progress: number;
    current_step?: string;
    error_message?: string;
    triggered_by?: string;
    priority: number;
    parent_job_id?: string;
    child_job_id?: string;
    started_at?: string;
    completed_at?: string;
    created_at: string;
}

// Individual step within a job
export interface JobStep {
    id: string;
    step_name: string;
    status: string;
    started_at?: string;
    completed_at?: string;
    duration_seconds?: number;
    details?: Record<string, unknown>;
}

// AI extraction log for debugging
export interface ExtractionLog {
    prompt: string;
    response: unknown;
    file_metadata: {
        path: string;
        name: string;
        format: string;
        size_bytes: number;
        pages?: number;
    };
    model?: string | null;
    mode: "vision" | "text" | "fallback";
    usage?: {
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
    } | null;
}

// Extended job details (includes steps and extraction logs)
export interface JobDetails extends Job {
    dno_slug?: string;
    updated_at?: string;
    steps: JobStep[];
    extraction_log?: ExtractionLog;
    parent_job?: {
        id: string;
        job_type: string;
        status: string;
    };
    child_job?: {
        id: string;
        job_type: string;
        status: string;
    };
}

// Job list item (from jobs endpoint)
export interface JobListItem {
    job_id: string;
    dno_id: string;
    dno_name?: string;
    year: number;
    data_type: string;
    status: string;
    progress: number;
    current_step?: string;
    error_message?: string;
    queue_position?: number;
    started_at?: string;
    completed_at?: string;
    created_at?: string;
}
