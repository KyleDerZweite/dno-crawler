import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Shield,
  Database,
  Activity,
  ExternalLink,
  AlertTriangle,
  Zap,
  Clock,
  FileText,
  Play,
  XCircle,
  ChevronDown,
  Loader2,
  CheckCircle2,
  FileWarning,
  HardDrive,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export function AdminPage() {
  const { isAdmin } = useAuth();

  const { data: dashboardResponse, isLoading: statsLoading } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: api.admin.getDashboard,
    enabled: isAdmin(),
  });

  const { data: flaggedResponse, isLoading: flaggedLoading } = useQuery({
    queryKey: ["admin", "flagged"],
    queryFn: api.admin.getFlagged,
    enabled: isAdmin(),
  });

  const stats = dashboardResponse?.data;
  const flaggedItems = flaggedResponse?.data?.items || [];

  // Parse structured flag reason for display
  const parseFlagReason = (reason?: string | null) => {
    if (!reason) return null;

    const parts: { issue?: string; fields?: string; notes?: string } = {};
    reason.split(" | ").forEach(part => {
      if (part.startsWith("Issue: ")) parts.issue = part.replace("Issue: ", "");
      else if (part.startsWith("Fields: ")) parts.fields = part.replace("Fields: ", "");
      else if (part.startsWith("Notes: ")) parts.notes = part.replace("Notes: ", "");
    });

    return parts;
  };

  if (!isAdmin()) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md p-8 text-center">
          <Shield className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
          <p className="text-muted-foreground">
            You need administrator privileges to access this page.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <Card className="p-5">
        <CardTitle className="font-semibold flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          Admin Dashboard
        </CardTitle>
        <p className="text-muted-foreground text-sm mt-2">System administration and monitoring</p>
      </Card>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          icon={Database}
          title="Total DNOs"
          value={stats?.dnos.total || 0}
          color="text-warning"
          bg="bg-warning/20"
          loading={statsLoading}
        />
        <StatCard
          icon={Activity}
          title="Running Jobs"
          value={stats?.jobs.running || 0}
          color="text-success"
          bg="bg-success/20"
          loading={statsLoading}
        />
        <StatCard
          icon={Activity}
          title="Pending Jobs"
          value={stats?.jobs.pending || 0}
          color="text-secondary-foreground"
          bg="bg-secondary"
          loading={statsLoading}
        />
        <StatCard
          icon={AlertTriangle}
          title="Flagged Items"
          value={stats?.flagged?.total || 0}
          color="text-amber-500"
          bg="bg-amber-500/20"
          loading={statsLoading}
        />
      </div>

      {/* Flagged Items Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Flagged Items
            {stats?.flagged?.total ? (
              <Badge variant="secondary" className="ml-2 bg-amber-500/20 text-amber-600">
                {stats.flagged.total}
              </Badge>
            ) : null}
          </CardTitle>
          <CardDescription>Data records flagged for review</CardDescription>
        </CardHeader>
        <CardContent>
          {flaggedLoading ? (
            <p className="text-muted-foreground text-center py-8">Loading...</p>
          ) : flaggedItems.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No flagged items</p>
            </div>
          ) : (
            <div className="space-y-2">
              <TooltipProvider>
                {flaggedItems.map((item) => {
                  const parsed = parseFlagReason(item.flag_reason);
                  return (
                    <Tooltip key={`${item.type}-${item.id}`}>
                      <TooltipTrigger asChild>
                        <Link
                          to={`/dnos/${item.dno_id}`}
                          className="flex items-center justify-between p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${item.type === "netzentgelte" ? "bg-blue-500/10 text-blue-500" : "bg-purple-500/10 text-purple-500"}`}>
                              {item.type === "netzentgelte" ? <Zap className="h-4 w-4" /> : <Clock className="h-4 w-4" />}
                            </div>
                            <div>
                              <p className="font-medium text-sm">{item.dno_name}</p>
                              <p className="text-xs text-muted-foreground">
                                {item.type === "netzentgelte" ? "Netzentgelte" : "HLZF"} • {item.voltage_level} • {item.year}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {parsed?.issue && (
                              <Badge variant="outline" className="text-xs border-amber-500/50 text-amber-600">
                                {parsed.issue}
                              </Badge>
                            )}
                            {item.flagged_at && (
                              <span className="text-xs text-muted-foreground">
                                {new Date(item.flagged_at).toLocaleDateString("de-DE")}
                              </span>
                            )}
                          </div>
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <div className="space-y-1.5">
                          <div className="font-medium text-amber-400">⚠ Flag Details</div>
                          {parsed?.issue && (
                            <div className="text-xs">
                              <span className="text-muted-foreground">Issue:</span>{" "}
                              <span className="font-medium">{parsed.issue}</span>
                            </div>
                          )}
                          {parsed?.fields && (
                            <div className="text-xs">
                              <span className="text-muted-foreground">Fields:</span>{" "}
                              <span>{parsed.fields}</span>
                            </div>
                          )}
                          {parsed?.notes && (
                            <div className="text-xs">
                              <span className="text-muted-foreground">Notes:</span>{" "}
                              <span className="italic">{parsed.notes}</span>
                            </div>
                          )}
                          {!parsed?.issue && item.flag_reason && (
                            <div className="text-xs opacity-80">{item.flag_reason}</div>
                          )}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </TooltipProvider>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cached Files & Bulk Extraction */}
      <CachedFilesSection />

      {/* User Management Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            User Management
          </CardTitle>
          <CardDescription>Users are managed through Zitadel</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 border border-border/50 rounded-lg bg-muted/20">
            <div>
              <p className="font-medium">Zitadel Console</p>
              <p className="text-sm text-muted-foreground">
                Manage users, roles, and authentication settings in the centralized identity provider.
              </p>
            </div>
            <Button variant="outline" asChild>
              <a
                href={import.meta.env.VITE_ZITADEL_AUTHORITY}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="mr-2 h-4 w-4" />
                Open Zitadel
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ icon: Icon, title, value, color, bg, loading }: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  value: number;
  color: string;
  bg: string;
  loading: boolean;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-full ${bg}`}>
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
        <div>
          <div className="text-2xl font-bold">
            {loading ? "..." : value}
          </div>
          <p className="text-muted-foreground text-sm">{title}</p>
        </div>
      </div>
    </Card>
  )
}

// ==============================================================================
// Cached Files & Bulk Extraction Section
// ==============================================================================

type ExtractMode = "flagged_only" | "default" | "force_override";

function CachedFilesSection() {
  const queryClient = useQueryClient();
  const [showPreview, setShowPreview] = useState(false);
  const [selectedMode, setSelectedMode] = useState<ExtractMode>("default");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [selectedFormats, setSelectedFormats] = useState<string[]>([]);
  const [selectedDataTypes, setSelectedDataTypes] = useState<string[]>(["netzentgelte", "hlzf"]);

  // Fetch cached files stats
  const { data: filesResponse, isLoading: filesLoading } = useQuery({
    queryKey: ["admin", "cached-files"],
    queryFn: api.admin.getCachedFiles,
    refetchInterval: 30000, // Refresh every 30s
  });

  // Fetch bulk extract status
  const { data: bulkStatusResponse } = useQuery({
    queryKey: ["admin", "bulk-extract-status"],
    queryFn: api.admin.getBulkExtractStatus,
    refetchInterval: 5000, // Refresh every 5s for progress
  });

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: () => api.admin.previewBulkExtract({
      mode: selectedMode,
      data_types: selectedDataTypes,
      formats: selectedFormats.length > 0 ? selectedFormats : undefined,
    }),
  });

  // Trigger extraction mutation
  const extractMutation = useMutation({
    mutationFn: () => api.admin.triggerBulkExtract({
      mode: selectedMode,
      data_types: selectedDataTypes,
      formats: selectedFormats.length > 0 ? selectedFormats : undefined,
    }),
    onSuccess: () => {
      setShowPreview(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "bulk-extract-status"] });
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: api.admin.cancelBulkExtract,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "bulk-extract-status"] });
    },
  });

  const filesData = filesResponse?.data;
  const bulkStatus = bulkStatusResponse?.data;
  const previewData = previewMutation.data?.data;
  const availableFormats = Object.keys(filesData?.by_format || {});

  const handleOpenPreview = async () => {
    await previewMutation.mutateAsync();
    setShowPreview(true);
  };

  const hasPendingJobs = (bulkStatus?.pending || 0) > 0 || (bulkStatus?.running || 0) > 0;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5 text-primary" />
            Cached Files & Bulk Extraction
          </CardTitle>
          <CardDescription>
            Manage downloaded files and trigger bulk data extraction
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* File Stats */}
          <div className="grid gap-3 md:grid-cols-4">
            <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/20">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <div>
                <div className="text-xl font-bold">
                  {filesLoading ? "..." : filesData?.total_files || 0}
                </div>
                <p className="text-xs text-muted-foreground">Total Files</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/20">
              <FileWarning className="h-5 w-5 text-amber-500" />
              <div>
                <div className="text-xl font-bold text-amber-500">
                  {filesLoading ? "..." : filesData?.by_status.no_data || 0}
                </div>
                <p className="text-xs text-muted-foreground">No Data</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/20">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              <div>
                <div className="text-xl font-bold text-orange-500">
                  {filesLoading ? "..." : filesData?.by_status.flagged || 0}
                </div>
                <p className="text-xs text-muted-foreground">Flagged</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/20">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              <div>
                <div className="text-xl font-bold text-green-500">
                  {filesLoading ? "..." : filesData?.by_status.verified || 0}
                </div>
                <p className="text-xs text-muted-foreground">Verified</p>
              </div>
            </div>
          </div>

          {/* Bulk Extraction Controls */}
          <div className="p-4 rounded-lg border bg-muted/10 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium">Bulk Extraction</h4>
                <p className="text-sm text-muted-foreground">
                  Extract data from all cached files based on mode
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Select
                  value={selectedMode}
                  onValueChange={(v) => setSelectedMode(v as ExtractMode)}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="flagged_only">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                        Flagged Only
                      </div>
                    </SelectItem>
                    <SelectItem value="default">
                      <div className="flex items-center gap-2">
                        <Zap className="h-4 w-4 text-blue-500" />
                        Default
                      </div>
                    </SelectItem>
                    <SelectItem value="force_override">
                      <div className="flex items-center gap-2">
                        <XCircle className="h-4 w-4 text-red-500" />
                        Force Override
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  onClick={handleOpenPreview}
                  disabled={previewMutation.isPending || filesLoading}
                >
                  {previewMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  Preview & Start
                </Button>
              </div>
            </div>

            {/* Mode explanation */}
            <div className="text-xs text-muted-foreground bg-muted/50 p-2 rounded">
              {selectedMode === "flagged_only" && (
                <span>Only re-extract files where data has been flagged as incorrect.</span>
              )}
              {selectedMode === "default" && (
                <span>Extract files with no data, flagged data, or unverified data. <strong>Verified data is protected.</strong></span>
              )}
              {selectedMode === "force_override" && (
                <span className="text-red-500">⚠️ Override ALL data including verified records. Use with caution!</span>
              )}
            </div>

            {/* Advanced Options */}
            <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
              <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
                <ChevronDown className={`h-4 w-4 transition-transform ${advancedOpen ? "rotate-180" : ""}`} />
                Advanced Options
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-3 space-y-3">
                <div className="grid gap-4 md:grid-cols-2">
                  {/* Data Types */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Data Types</label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={selectedDataTypes.includes("netzentgelte")}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedDataTypes([...selectedDataTypes, "netzentgelte"]);
                            } else {
                              setSelectedDataTypes(selectedDataTypes.filter(t => t !== "netzentgelte"));
                            }
                          }}
                        />
                        Netzentgelte
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={selectedDataTypes.includes("hlzf")}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedDataTypes([...selectedDataTypes, "hlzf"]);
                            } else {
                              setSelectedDataTypes(selectedDataTypes.filter(t => t !== "hlzf"));
                            }
                          }}
                        />
                        HLZF
                      </label>
                    </div>
                  </div>
                  {/* File Formats */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">File Formats</label>
                    <div className="flex gap-4 flex-wrap">
                      {availableFormats.map((format) => (
                        <label key={format} className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={selectedFormats.includes(format)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedFormats([...selectedFormats, format]);
                              } else {
                                setSelectedFormats(selectedFormats.filter(f => f !== format));
                              }
                            }}
                          />
                          {format.toUpperCase()}
                        </label>
                      ))}
                      {availableFormats.length === 0 && (
                        <span className="text-sm text-muted-foreground">No files found</span>
                      )}
                    </div>
                    {selectedFormats.length === 0 && availableFormats.length > 0 && (
                      <p className="text-xs text-muted-foreground mt-1">All formats selected by default</p>
                    )}
                  </div>
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>

          {/* Bulk Job Progress */}
          {(bulkStatus?.total || 0) > 0 && (
            <div className="p-4 rounded-lg border space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-primary" />
                  <h4 className="font-medium">Bulk Extraction Progress</h4>
                </div>
                {hasPendingJobs && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => cancelMutation.mutate()}
                    disabled={cancelMutation.isPending}
                  >
                    {cancelMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <XCircle className="mr-2 h-4 w-4" />
                    )}
                    Cancel Pending
                  </Button>
                )}
              </div>
              <Progress value={bulkStatus?.progress_percent || 0} className="h-2" />
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>{bulkStatus?.progress_percent || 0}% complete</span>
                <span>
                  {bulkStatus?.completed || 0} / {bulkStatus?.total || 0} jobs
                  {(bulkStatus?.failed || 0) > 0 && (
                    <span className="text-red-500 ml-2">({bulkStatus?.failed} failed)</span>
                  )}
                </span>
              </div>
              <div className="flex gap-4 text-xs">
                <span className="flex items-center gap-1">
                  <div className="h-2 w-2 rounded-full bg-yellow-500" />
                  Pending: {bulkStatus?.pending || 0}
                </span>
                <span className="flex items-center gap-1">
                  <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                  Running: {bulkStatus?.running || 0}
                </span>
                <span className="flex items-center gap-1">
                  <div className="h-2 w-2 rounded-full bg-green-500" />
                  Completed: {bulkStatus?.completed || 0}
                </span>
                {(bulkStatus?.failed || 0) > 0 && (
                  <span className="flex items-center gap-1">
                    <div className="h-2 w-2 rounded-full bg-red-500" />
                    Failed: {bulkStatus?.failed || 0}
                  </span>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preview Dialog */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Play className="h-5 w-5" />
              Bulk Extraction Preview
            </DialogTitle>
            <DialogDescription>
              Review what will be extracted before starting
            </DialogDescription>
          </DialogHeader>

          {previewData && (
            <div className="space-y-4">
              {/* Summary Stats */}
              <div className="grid gap-3 md:grid-cols-3">
                <div className="p-3 rounded-lg border bg-muted/20 text-center">
                  <div className="text-2xl font-bold">{previewData.total_files}</div>
                  <p className="text-xs text-muted-foreground">Total Files Scanned</p>
                </div>
                <div className="p-3 rounded-lg border bg-primary/10 text-center">
                  <div className="text-2xl font-bold text-primary">{previewData.will_extract}</div>
                  <p className="text-xs text-muted-foreground">Jobs to Queue</p>
                </div>
                {selectedMode !== "force_override" && previewData.protected_verified > 0 && (
                  <div className="p-3 rounded-lg border bg-green-500/10 text-center">
                    <div className="text-2xl font-bold text-green-500">{previewData.protected_verified}</div>
                    <p className="text-xs text-muted-foreground">Protected (Verified)</p>
                  </div>
                )}
                {selectedMode === "force_override" && previewData.will_override_verified > 0 && (
                  <div className="p-3 rounded-lg border bg-red-500/10 text-center">
                    <div className="text-2xl font-bold text-red-500">{previewData.will_override_verified}</div>
                    <p className="text-xs text-muted-foreground">Will Override Verified!</p>
                  </div>
                )}
              </div>

              {/* Breakdown */}
              <div className="p-3 rounded-lg bg-muted/30 space-y-2">
                <h4 className="font-medium text-sm">Breakdown by Status</h4>
                <div className="grid gap-2 md:grid-cols-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">No existing data:</span>
                    <span>{previewData.no_data}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Flagged:</span>
                    <span className="text-amber-500">{previewData.flagged}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Unverified:</span>
                    <span>{previewData.unverified}</span>
                  </div>
                </div>
              </div>

              {/* Mode Info */}
              <div className={`p-3 rounded-lg text-sm ${selectedMode === "force_override" ? "bg-red-500/10 border border-red-500/30" : "bg-blue-500/10"}`}>
                <strong>Mode: </strong>
                {selectedMode === "flagged_only" && "Only re-extracting flagged data"}
                {selectedMode === "default" && "Default mode - verified data is protected"}
                {selectedMode === "force_override" && (
                  <span className="text-red-500">
                    ⚠️ Force Override - ALL data including {previewData.will_override_verified} verified records will be overwritten!
                  </span>
                )}
              </div>

              {/* Info about priority */}
              <p className="text-xs text-muted-foreground">
                Jobs will be queued with lower priority so they don't block regular extraction jobs.
              </p>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPreview(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending || (previewData?.will_extract || 0) === 0}
              variant={selectedMode === "force_override" ? "destructive" : "default"}
            >
              {extractMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Queue {previewData?.will_extract || 0} Jobs
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}