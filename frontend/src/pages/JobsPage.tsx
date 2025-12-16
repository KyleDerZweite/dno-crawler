import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Job, type JobDetails, type DNO } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Activity,
  Plus,
  RefreshCw,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronRight,
  ArrowLeft,
  Play,
  Trash2,
  FileText,
  Calendar,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";

type JobStatus = Job["status"];

const statusConfig: Record<JobStatus, { label: string; color: string; icon: React.ElementType }> = {
  pending: { label: "Pending", color: "bg-yellow-500/20 text-yellow-600 border-yellow-500/30", icon: Clock },
  running: { label: "Running", color: "bg-blue-500/20 text-blue-600 border-blue-500/30", icon: Loader2 },
  completed: { label: "Completed", color: "bg-green-500/20 text-green-600 border-green-500/30", icon: CheckCircle },
  failed: { label: "Failed", color: "bg-red-500/20 text-red-600 border-red-500/30", icon: XCircle },
  cancelled: { label: "Cancelled", color: "bg-gray-500/20 text-gray-600 border-gray-500/30", icon: AlertCircle },
};

export function JobsPage() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const isAdminUser = isAdmin();

  // Fetch jobs list using unified jobs API
  const { data: jobsResponse, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs", statusFilter],
    queryFn: () => api.jobs.list({
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: 50
    }),
    refetchInterval: 5000, // Refresh every 5 seconds for live updates
  });

  const jobs = jobsResponse?.jobs || [];
  const queueLength = jobsResponse?.queue_length || 0;

  // Rerun mutation
  const rerunMutation = useMutation({
    mutationFn: (jobId: string) => api.jobs.rerun(jobId),
    onSuccess: (data) => {
      toast({
        title: "Job rerun created",
        description: `New job ID: ${data.data.job_id}`,
      });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error: unknown) => {
      const message = error instanceof AxiosError
        ? error.response?.data?.detail ?? error.message
        : "Unknown error";
      toast({ variant: "destructive", title: "Failed to rerun job", description: message });
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => api.jobs.cancel(jobId),
    onSuccess: () => {
      toast({ title: "Job cancelled" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error: unknown) => {
      const message = error instanceof AxiosError
        ? error.response?.data?.detail ?? error.message
        : "Unknown error";
      toast({ variant: "destructive", title: "Failed to cancel job", description: message });
    },
  });

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
        <CreateJobDialog
          open={createDialogOpen}
          onOpenChange={setCreateDialogOpen}
        />
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
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Job
          </Button>
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
  status: string;
  progress: number;
  current_step?: string;
  error_message?: string;
  queue_position?: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
};

function CrawlJobCard({ job, onClick }: { job: CrawlJobItem; onClick: () => void }) {
  const status = job.status as keyof typeof statusConfig;
  const config = statusConfig[status] || statusConfig["pending"];
  const StatusIcon = config.icon;

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
            </div>
            <div className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
              {job.queue_position && (
                <Badge variant="outline" className="text-xs">
                  Queue #{job.queue_position}
                </Badge>
              )}
              <span>{job.current_step || "Waiting to start"}</span>
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

// Keep the old JobCard for legacy use (from CrawlJobModel)
function JobCard({ job, onClick }: { job: Job; onClick: () => void }) {
  const config = statusConfig[job.status];
  const StatusIcon = config.icon;

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
              <span className="font-semibold">{job.dno_name || `DNO ${job.dno_id}`}</span>
              <Badge variant="outline">{job.year}</Badge>
              <Badge variant="secondary">{job.data_type}</Badge>
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              {job.current_step || "Waiting to start"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Progress bar for running jobs */}
          {job.status === "running" && (
            <div className="w-32">
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${job.progress}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground">{job.progress}%</span>
            </div>
          )}

          <div className="text-right text-sm text-muted-foreground">
            <div>{new Date(job.created_at).toLocaleDateString()}</div>
            <div>{new Date(job.created_at).toLocaleTimeString()}</div>
          </div>

          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </div>
      </div>
    </Card>
  );
}

function JobDetailView({
  job,
  onBack,
  onRerun,
  onCancel,
  isRerunning,
  isCancelling,
}: {
  job: JobDetails;
  loading?: boolean;
  onBack: () => void;
  onRerun: () => void;
  onCancel: () => void;
  isRerunning: boolean;
  isCancelling: boolean;
}) {
  const config = statusConfig[job.status];
  const StatusIcon = config.icon;

  return (
    <div className="space-y-6">
      {/* Back button and header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={onBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">Job #{job.id}</h1>
          <p className="text-muted-foreground">{job.dno_name}</p>
        </div>
        <div className="flex gap-2">
          {(job.status === "failed" || job.status === "completed" || job.status === "cancelled") && (
            <Button variant="outline" onClick={onRerun} disabled={isRerunning}>
              {isRerunning ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Rerun
            </Button>
          )}
          {(job.status === "pending" || job.status === "running") && (
            <Button variant="destructive" onClick={onCancel} disabled={isCancelling}>
              {isCancelling ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Status and info */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <div className="text-sm text-muted-foreground mb-1">Status</div>
          <div className="flex items-center gap-2">
            <Badge className={config.color}>
              <StatusIcon className={cn("h-3 w-3 mr-1", job.status === "running" && "animate-spin")} />
              {config.label}
            </Badge>
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground mb-1">Progress</div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${job.progress}%` }}
              />
            </div>
            <span className="font-semibold">{job.progress}%</span>
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground mb-1">Year</div>
          <div className="font-semibold flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            {job.year}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground mb-1">Data Type</div>
          <div className="font-semibold flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {job.data_type}
          </div>
        </Card>
      </div>

      {/* Error message if failed */}
      {job.error_message && (
        <Card className="p-4 border-red-500/30 bg-red-500/10">
          <div className="flex items-start gap-3">
            <XCircle className="h-5 w-5 text-red-500 mt-0.5" />
            <div>
              <div className="font-semibold text-red-500">Error</div>
              <div className="text-sm text-muted-foreground mt-1">{job.error_message}</div>
            </div>
          </div>
        </Card>
      )}

      {/* Current step */}
      {job.current_step && (
        <Card className="p-4">
          <div className="text-sm text-muted-foreground mb-1">Current Step</div>
          <div className="font-medium">{job.current_step}</div>
        </Card>
      )}

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <TimelineItem
              label="Created"
              time={job.created_at}
              icon={<Clock className="h-4 w-4" />}
            />
            {job.started_at && (
              <TimelineItem
                label="Started"
                time={job.started_at}
                icon={<Play className="h-4 w-4" />}
              />
            )}
            {job.completed_at && (
              <TimelineItem
                label={job.status === "completed" ? "Completed" : job.status === "failed" ? "Failed" : "Ended"}
                time={job.completed_at}
                icon={job.status === "completed" ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Steps */}
      {job.steps && job.steps.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Steps</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {job.steps.map((step, index) => (
                <div key={step.id} className="flex items-center gap-4 p-3 rounded-lg bg-secondary/30">
                  <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-sm font-medium">
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{step.step_name}</div>
                    {step.duration_seconds && (
                      <div className="text-sm text-muted-foreground">
                        Duration: {step.duration_seconds}s
                      </div>
                    )}
                  </div>
                  <Badge variant={step.status === "completed" ? "default" : "secondary"}>
                    {step.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TimelineItem({ label, time, icon }: { label: string; time: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <div className="p-2 rounded-full bg-secondary">{icon}</div>
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-sm text-muted-foreground">
          {new Date(time).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

function CreateJobDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [dnoId, setDnoId] = useState("");
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [dataType, setDataType] = useState("all");
  const [jobType, setJobType] = useState("crawl");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Fetch DNOs for the dropdown
  const { data: dnosResponse } = useQuery({
    queryKey: ["dnos"],
    queryFn: () => api.dnos.list(),
  });
  const dnos = dnosResponse?.data || [];

  const createMutation = useMutation({
    mutationFn: () => api.admin.createJob({
      dno_id: parseInt(dnoId),
      year: parseInt(year),
      data_type: dataType,
      job_type: jobType,
    }),
    onSuccess: (data) => {
      toast({
        title: "Job created",
        description: `Job ID: ${data.data.job_id}`,
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
      onOpenChange(false);
      setDnoId("");
      setYear(new Date().getFullYear().toString());
      setDataType("all");
      setJobType("crawl");
    },
    onError: (error: unknown) => {
      const message = error instanceof AxiosError
        ? error.response?.data?.detail ?? error.message
        : "Unknown error";
      toast({ variant: "destructive", title: "Failed to create job", description: message });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Create Job
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Job</DialogTitle>
          <DialogDescription>
            Create a standalone extraction job for a specific DNO and year.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>DNO</Label>
            <Select value={dnoId} onValueChange={setDnoId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a DNO" />
              </SelectTrigger>
              <SelectContent>
                {dnos.map((dno: DNO) => (
                  <SelectItem key={dno.id} value={dno.id}>
                    {dno.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Year</Label>
            <Input
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              min={2020}
              max={2030}
            />
          </div>

          <div className="space-y-2">
            <Label>Data Type</Label>
            <Select value={dataType} onValueChange={setDataType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="netzentgelte">Netzentgelte only</SelectItem>
                <SelectItem value="hlzf">HLZF only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Job Type</Label>
            <Select value={jobType} onValueChange={setJobType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="crawl">Full Crawl</SelectItem>
                <SelectItem value="rescan_pdf">Rescan PDF</SelectItem>
                <SelectItem value="rerun_extraction">Rerun Extraction</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={!dnoId || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            Create Job
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
