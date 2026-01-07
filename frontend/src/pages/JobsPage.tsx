import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Card,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Activity,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

const statusConfig: Record<JobStatus, { label: string; color: string; icon: React.ElementType }> = {
  pending: { label: "Pending", color: "bg-yellow-500/20 text-yellow-600 border-yellow-500/30", icon: Clock },
  running: { label: "Running", color: "bg-blue-500/20 text-blue-600 border-blue-500/30", icon: Loader2 },
  completed: { label: "Completed", color: "bg-green-500/20 text-green-600 border-green-500/30", icon: CheckCircle },
  failed: { label: "Failed", color: "bg-red-500/20 text-red-600 border-red-500/30", icon: XCircle },
  cancelled: { label: "Cancelled", color: "bg-gray-500/20 text-gray-500 border-gray-500/30", icon: AlertCircle },
};

export function JobsPage() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const isAdminUser = isAdmin();

  // Fetch jobs list using unified jobs API
  const { data: jobsResponse, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs", statusFilter],
    queryFn: () => api.jobs.list({
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: 50
    }),
    refetchOnMount: "always", // Always fetch fresh data when page opens
    refetchInterval: 5000, // Refresh every 5 seconds for live updates
  });

  const jobs = jobsResponse?.jobs || [];

  if (!isAdminUser) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md p-8 text-center">
          <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
          <p className="text-muted-foreground">
            You need administrator privileges to access the jobs page.
          </p>
        </Card>
      </div>
    );
  }

  // Detail view - navigate to job detail page
  const handleJobClick = (job: typeof jobs[0]) => {
    navigate(`/jobs/${job.job_id}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Jobs</h1>
          <p className="text-muted-foreground mt-1">
            Monitor and manage crawl jobs
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex gap-4 items-center">
          <Label className="text-sm text-muted-foreground">Status:</Label>
          <div className="flex gap-2">
            {["all", "pending", "running", "completed", "failed", "cancelled"].map((status) => (
              <Button
                key={status}
                variant={statusFilter === status ? "default" : "outline"}
                size="sm"
                onClick={() => setStatusFilter(status)}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {/* Jobs List */}
      {jobsLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : jobs.length === 0 ? (
        <Card className="p-12 text-center">
          <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No jobs found</h3>
          <p className="text-muted-foreground mb-4">
            {statusFilter !== "all"
              ? `No ${statusFilter} jobs at the moment.`
              : "No extraction jobs have been created yet."}
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <CrawlJobCard
              key={job.job_id}
              job={job}
              onClick={() => handleJobClick(job)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Type for crawl jobs from the unified API
type CrawlJobItem = {
  job_id: string;
  dno_id: string;
  dno_name?: string;
  year: number;
  data_type: string;
  job_type?: 'full' | 'crawl' | 'extract';
  status: string;
  progress: number;
  current_step?: string;
  error_message?: string;
  queue_position?: number;
  parent_job_id?: string;
  child_job_id?: string;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
};

// Job type badge config
const jobTypeConfig: Record<string, { label: string; color: string }> = {
  full: { label: 'Full', color: 'bg-purple-500/20 text-purple-600 border-purple-500/30' },
  crawl: { label: 'Crawl', color: 'bg-orange-500/20 text-orange-600 border-orange-500/30' },
  extract: { label: 'Extract', color: 'bg-teal-500/20 text-teal-600 border-teal-500/30' },
};

function CrawlJobCard({ job, onClick }: { job: CrawlJobItem; onClick: () => void }) {
  const status = job.status as keyof typeof statusConfig;
  const config = statusConfig[status] || statusConfig["pending"];
  const StatusIcon = config.icon;
  const jobType = job.job_type || 'full';
  const typeConfig = jobTypeConfig[jobType] || jobTypeConfig.full;

  return (
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className={cn("p-2 rounded-lg", config.color)}>
            <StatusIcon className={cn("h-5 w-5", job.status === "running" && "animate-spin")} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold">{job.dno_name || `Job ${job.job_id.slice(0, 8)}`}</span>
              <Badge variant="outline">{job.year}</Badge>
              <Badge variant="secondary">{job.data_type}</Badge>
              <Badge className={cn("text-xs", typeConfig.color)} variant="outline">
                {typeConfig.label}
              </Badge>
            </div>
            <div className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
              {job.queue_position && (
                <Badge variant="outline" className="text-xs">
                  Queue #{job.queue_position}
                </Badge>
              )}
              <span>{job.current_step || "Waiting to start"}</span>
              {job.child_job_id && (
                <Badge variant="outline" className="text-xs">
                  → Extract #{job.child_job_id}
                </Badge>
              )}
              {job.parent_job_id && (
                <Badge variant="outline" className="text-xs">
                  ← Crawl #{job.parent_job_id}
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {job.created_at && (
            <div className="text-right text-sm text-muted-foreground">
              <div>{new Date(job.created_at).toLocaleDateString()}</div>
              <div>{new Date(job.created_at).toLocaleTimeString()}</div>
            </div>
          )}
          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </div>
      </div>
    </Card>
  );
}
