import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft,
    Database,
    ExternalLink,
    RefreshCw,
    Loader2,
    Calendar,
    Zap,
    Clock,
    CheckCircle,
    XCircle,
    AlertCircle,
    Trash2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

export function DNODetailPage() {
    const { id } = useParams<{ id: string }>();
    const queryClient = useQueryClient();
    const { toast } = useToast();

    // Fetch DNO details
    const { data: dnoResponse, isLoading: dnoLoading, error: dnoError } = useQuery({
        queryKey: ["dno", id],
        queryFn: () => api.dnos.get(id!),
        enabled: !!id,
    });

    // Fetch DNO data (netzentgelte, hlzf)
    const { data: dataResponse, isLoading: dataLoading } = useQuery({
        queryKey: ["dno-data", id],
        queryFn: () => api.dnos.getData(id!),
        enabled: !!id,
    });

    // Fetch DNO crawl jobs
    const { data: jobsResponse, isLoading: jobsLoading } = useQuery({
        queryKey: ["dno-jobs", id],
        queryFn: () => api.dnos.getJobs(id!, 20),
        enabled: !!id,
    });

    const triggerCrawlMutation = useMutation({
        mutationFn: () => api.dnos.triggerCrawl(id!, { year: new Date().getFullYear() }),
        onSuccess: () => {
            toast({
                title: "Crawl triggered",
                description: "The crawler job has been queued",
            });
            queryClient.invalidateQueries({ queryKey: ["dno-jobs", id] });
        },
        onError: (error: unknown) => {
            const message =
                error instanceof AxiosError
                    ? error.response?.data?.detail ?? error.message
                    : error instanceof Error
                        ? error.message
                        : "Unknown error";
            toast({
                variant: "destructive",
                title: "Failed to trigger crawl",
                description: message,
            });
        },
    });

    const dno = dnoResponse?.data;
    const dnoData = dataResponse?.data;
    const jobs = jobsResponse?.data || [];

    // Get admin status
    const { isAdmin } = useAuth();

    // Delete Netzentgelte mutation
    const deleteNetzentgelteMutation = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteNetzentgelte(id!, recordId),
        onSuccess: () => {
            toast({
                title: "Record deleted",
                description: "The Netzentgelte record has been deleted",
            });
            queryClient.invalidateQueries({ queryKey: ["dno-data", id] });
        },
        onError: (error: unknown) => {
            const message =
                error instanceof AxiosError
                    ? error.response?.data?.detail ?? error.message
                    : error instanceof Error
                        ? error.message
                        : "Unknown error";
            toast({
                variant: "destructive",
                title: "Failed to delete record",
                description: message,
            });
        },
    });

    const handleDeleteNetzentgelte = (recordId: number) => {
        if (confirm("Are you sure you want to delete this record?")) {
            deleteNetzentgelteMutation.mutate(recordId);
        }
    };

    if (dnoLoading) {
        return (
            <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (dnoError || !dno) {
        return (
            <div className="space-y-4">
                <Link to="/dnos" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to DNOs
                </Link>
                <Card className="p-6 bg-destructive/10 border-destructive/20">
                    <p className="text-destructive text-center">
                        DNO not found or error loading data
                    </p>
                </Card>
            </div>
        );
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "completed":
                return <CheckCircle className="h-4 w-4 text-success" />;
            case "failed":
                return <XCircle className="h-4 w-4 text-destructive" />;
            case "running":
                return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
            case "pending":
                return <Clock className="h-4 w-4 text-muted-foreground" />;
            default:
                return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
        }
    };

    const getStatusBadge = (status: string) => {
        const variants: Record<string, string> = {
            completed: "bg-success/10 text-success border-success/20",
            failed: "bg-destructive/10 text-destructive border-destructive/20",
            running: "bg-primary/10 text-primary border-primary/20",
            pending: "bg-muted text-muted-foreground border-muted",
            cancelled: "bg-muted text-muted-foreground border-muted",
        };
        return (
            <Badge variant="outline" className={cn("font-medium", variants[status] || variants.pending)}>
                {status}
            </Badge>
        );
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div className="space-y-2">
                    <Link to="/dnos" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors">
                        <ArrowLeft className="mr-2 h-4 w-4" />
                        Back to DNOs
                    </Link>
                    <div className="flex items-center gap-3">
                        <div className="p-3 rounded-xl bg-primary/10 text-primary">
                            <Database className="h-6 w-6" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-foreground">{dno.name}</h1>
                            {dno.region && (
                                <p className="text-muted-foreground">{dno.region}</p>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex gap-2">
                    {dno.website && (
                        <Button variant="outline" asChild>
                            <a href={dno.website} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="mr-2 h-4 w-4" />
                                Website
                            </a>
                        </Button>
                    )}
                    <Button
                        onClick={() => triggerCrawlMutation.mutate()}
                        disabled={triggerCrawlMutation.isPending}
                    >
                        {triggerCrawlMutation.isPending ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Triggering...
                            </>
                        ) : (
                            <>
                                <RefreshCw className="mr-2 h-4 w-4" />
                                Trigger Crawl
                            </>
                        )}
                    </Button>
                </div>
            </div>

            {/* Info Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
                            <Zap className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">Netzentgelte Records</p>
                            <p className="text-2xl font-bold">{dnoData?.netzentgelte?.length || 0}</p>
                        </div>
                    </div>
                </Card>
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-500">
                            <Clock className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">HLZF Records</p>
                            <p className="text-2xl font-bold">{dnoData?.hlzf?.length || 0}</p>
                        </div>
                    </div>
                </Card>
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-green-500/10 text-green-500">
                            <Calendar className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">Crawl Jobs</p>
                            <p className="text-2xl font-bold">{jobs.length}</p>
                        </div>
                    </div>
                </Card>
            </div>

            {/* DNO Details */}
            <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4">Details</h2>
                <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <dt className="text-sm text-muted-foreground">Slug</dt>
                        <dd className="font-mono text-sm">{dno.slug}</dd>
                    </div>
                    {dno.official_name && (
                        <div>
                            <dt className="text-sm text-muted-foreground">Official Name</dt>
                            <dd>{dno.official_name}</dd>
                        </div>
                    )}
                    {dno.description && (
                        <div className="md:col-span-2">
                            <dt className="text-sm text-muted-foreground">Description</dt>
                            <dd>{dno.description}</dd>
                        </div>
                    )}
                    {dno.website && (
                        <div>
                            <dt className="text-sm text-muted-foreground">Website</dt>
                            <dd>
                                <a href={dno.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                                    {dno.website}
                                </a>
                            </dd>
                        </div>
                    )}
                </dl>
            </Card>

            {/* Netzentgelte Data */}
            <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Zap className="h-5 w-5 text-blue-500" />
                    Netzentgelte
                </h2>
                {dataLoading ? (
                    <div className="flex justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : dnoData?.netzentgelte && dnoData.netzentgelte.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b">
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Year</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Voltage Level</th>
                                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">Leistung (€/kW)</th>
                                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">Arbeit (ct/kWh)</th>
                                    {isAdmin && <th className="text-right py-2 px-3 font-medium text-muted-foreground w-24">Actions</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {dnoData.netzentgelte.map((item, idx) => (
                                    <tr key={idx} className="border-b border-border/50 hover:bg-muted/50">
                                        <td className="py-2 px-3">{item.year}</td>
                                        <td className="py-2 px-3">{item.voltage_level}</td>
                                        <td className="py-2 px-3 text-right font-mono">{item.leistung?.toFixed(2) || "-"}</td>
                                        <td className="py-2 px-3 text-right font-mono">{item.arbeit?.toFixed(3) || "-"}</td>
                                        {isAdmin && (
                                            <td className="py-2 px-3 text-right">
                                                <div className="flex gap-1 justify-end">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-7 w-7 p-0"
                                                        onClick={() => handleDeleteNetzentgelte(item.id)}
                                                    >
                                                        <Trash2 className="h-4 w-4 text-destructive" />
                                                    </Button>
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">No Netzentgelte data available</p>
                )}
            </Card>

            {/* HLZF Data */}
            <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Clock className="h-5 w-5 text-purple-500" />
                    HLZF (Hochlastzeitfenster)
                </h2>
                {dataLoading ? (
                    <div className="flex justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : dnoData?.hlzf && dnoData.hlzf.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b">
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Year</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Voltage Level</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Winter</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Frühling</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Sommer</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Herbst</th>
                                </tr>
                            </thead>
                            <tbody>
                                {dnoData.hlzf.map((item, idx) => (
                                    <tr key={idx} className="border-b border-border/50 hover:bg-muted/50">
                                        <td className="py-2 px-3">{item.year}</td>
                                        <td className="py-2 px-3">{item.voltage_level}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.winter || "-"}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.fruehling || "-"}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.sommer || "-"}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.herbst || "-"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">No HLZF data available</p>
                )}
            </Card>

            {/* Recent Crawl Jobs */}
            <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-green-500" />
                    Recent Crawl Jobs
                </h2>
                {jobsLoading ? (
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
                                        <p className="font-medium">
                                            {job.year} - {job.data_type}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {new Date(job.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    {job.status === "running" && (
                                        <span className="text-sm text-muted-foreground">{job.progress}%</span>
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
        </div>
    );
}
