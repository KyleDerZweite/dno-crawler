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
    FileDown,
    MoreVertical,
    Pencil,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useState, useMemo, useRef, useEffect } from "react";

export function DNODetailPage() {
    const { id } = useParams<{ id: string }>();
    const queryClient = useQueryClient();
    const { toast } = useToast();

    // Filter state - default to 2024
    const [yearFilter, setYearFilter] = useState<number[]>([2024]);
    const [voltageLevelFilter, setVoltageLevelFilter] = useState<string[]>([]);

    // Dropdown menu state
    const [openMenuId, setOpenMenuId] = useState<string | null>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    // Edit modal state
    const [editModalOpen, setEditModalOpen] = useState(false);
    const [editModalType, setEditModalType] = useState<'netzentgelte' | 'hlzf'>('netzentgelte');
    const [editRecord, setEditRecord] = useState<{
        id: number;
        leistung?: number;
        arbeit?: number;
        winter?: string;
        fruehling?: string;
        sommer?: string;
        herbst?: string;
    } | null>(null);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setOpenMenuId(null);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Fetch DNO details
    const { data: dnoResponse, isLoading: dnoLoading, error: dnoError } = useQuery({
        queryKey: ["dno", id],
        queryFn: () => api.dnos.get(id!),
        enabled: !!id,
    });

    // Fetch DNO data (netzentgelte, hlzf)
    const { data: dataResponse, isLoading: dataLoading, refetch: refetchData } = useQuery({
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

    // Fetch available files
    const { data: filesResponse } = useQuery({
        queryKey: ["dno-files", id],
        queryFn: () => api.dnos.getFiles(id!),
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
    const files = filesResponse?.data || [];

    // Get admin status
    const { isAdmin } = useAuth();

    // Get unique years and voltage levels for filter options
    const filterOptions = useMemo(() => {
        const years = new Set<number>();
        const voltageLevels = new Set<string>();

        dnoData?.netzentgelte?.forEach(item => {
            years.add(item.year);
            if (item.voltage_level) voltageLevels.add(item.voltage_level);
        });
        dnoData?.hlzf?.forEach(item => {
            years.add(item.year);
            if (item.voltage_level) voltageLevels.add(item.voltage_level);
        });

        return {
            years: Array.from(years).sort((a, b) => b - a),
            voltageLevels: Array.from(voltageLevels).sort(),
        };
    }, [dnoData]);

    // Apply filters to data
    const filteredNetzentgelte = useMemo(() => {
        if (!dnoData?.netzentgelte) return [];
        return dnoData.netzentgelte.filter(item => {
            if (yearFilter.length > 0 && !yearFilter.includes(item.year)) return false;
            if (voltageLevelFilter.length > 0 && !voltageLevelFilter.includes(item.voltage_level)) return false;
            return true;
        });
    }, [dnoData?.netzentgelte, yearFilter, voltageLevelFilter]);

    const filteredHLZF = useMemo(() => {
        if (!dnoData?.hlzf) return [];
        return dnoData.hlzf.filter(item => {
            if (yearFilter.length > 0 && !yearFilter.includes(item.year)) return false;
            if (voltageLevelFilter.length > 0 && !voltageLevelFilter.includes(item.voltage_level)) return false;
            return true;
        });
    }, [dnoData?.hlzf, yearFilter, voltageLevelFilter]);

    // Toggle filter functions
    const toggleYearFilter = (year: number) => {
        setYearFilter(prev =>
            prev.includes(year)
                ? prev.filter(y => y !== year)
                : [...prev, year]
        );
    };

    // Delete Netzentgelte mutation
    const deleteNetzentgelteMutation = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteNetzentgelte(id!, recordId),
        onSuccess: () => {
            toast({
                title: "Record deleted",
                description: "The Netzentgelte record has been deleted",
            });
            refetchData();
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

    // Delete HLZF mutation
    const deleteHLZFMutation = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteHLZF(id!, recordId),
        onSuccess: () => {
            toast({
                title: "Record deleted",
                description: "The HLZF record has been deleted",
            });
            refetchData();
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

    const handleDeleteHLZF = (recordId: number) => {
        if (confirm("Are you sure you want to delete this record?")) {
            deleteHLZFMutation.mutate(recordId);
        }
    };

    // Update Netzentgelte mutation
    const updateNetzentgelteMutation = useMutation({
        mutationFn: (data: { id: number; leistung?: number; arbeit?: number }) =>
            api.dnos.updateNetzentgelte(id!, data.id, { leistung: data.leistung, arbeit: data.arbeit }),
        onSuccess: () => {
            toast({
                title: "Record updated",
                description: "The Netzentgelte record has been updated",
            });
            setEditModalOpen(false);
            setEditRecord(null);
            refetchData();
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
                title: "Failed to update record",
                description: message,
            });
        },
    });

    // Update HLZF mutation
    const updateHLZFMutation = useMutation({
        mutationFn: (data: { id: number; winter?: string; fruehling?: string; sommer?: string; herbst?: string }) =>
            api.dnos.updateHLZF(id!, data.id, { winter: data.winter, fruehling: data.fruehling, sommer: data.sommer, herbst: data.herbst }),
        onSuccess: () => {
            toast({
                title: "Record updated",
                description: "The HLZF record has been updated",
            });
            setEditModalOpen(false);
            setEditRecord(null);
            refetchData();
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
                title: "Failed to update record",
                description: message,
            });
        },
    });

    // Toggle voltage level filter
    const toggleVoltageLevelFilter = (level: string) => {
        setVoltageLevelFilter(prev =>
            prev.includes(level)
                ? prev.filter(l => l !== level)
                : [...prev, level]
        );
    };

    // Open edit modal for Netzentgelte
    const handleEditNetzentgelte = (item: { id: number; leistung?: number; arbeit?: number }) => {
        setEditModalType('netzentgelte');
        setEditRecord({ id: item.id, leistung: item.leistung, arbeit: item.arbeit });
        setEditModalOpen(true);
        setOpenMenuId(null);
    };

    // Open edit modal for HLZF
    const handleEditHLZF = (item: { id: number; winter?: string | null; fruehling?: string | null; sommer?: string | null; herbst?: string | null }) => {
        setEditModalType('hlzf');
        setEditRecord({ id: item.id, winter: item.winter || '', fruehling: item.fruehling || '', sommer: item.sommer || '', herbst: item.herbst || '' });
        setEditModalOpen(true);
        setOpenMenuId(null);
    };

    // Handle modal save
    const handleSaveEdit = () => {
        if (!editRecord) return;

        if (editModalType === 'netzentgelte') {
            updateNetzentgelteMutation.mutate({
                id: editRecord.id,
                leistung: editRecord.leistung,
                arbeit: editRecord.arbeit,
            });
        } else {
            updateHLZFMutation.mutate({
                id: editRecord.id,
                winter: editRecord.winter,
                fruehling: editRecord.fruehling,
                sommer: editRecord.sommer,
                herbst: editRecord.herbst,
            });
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

            {/* Filters */}
            <Card className="p-4">
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Database className="h-4 w-4" />
                        <span>Filters:</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">Year:</span>
                        <div className="flex gap-1">
                            {filterOptions.years.map(year => (
                                <button
                                    key={year}
                                    onClick={() => toggleYearFilter(year)}
                                    className={cn(
                                        "px-2.5 py-1 text-sm rounded-md transition-colors font-medium",
                                        yearFilter.includes(year)
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-muted hover:bg-muted/80 text-muted-foreground"
                                    )}
                                >
                                    {year}
                                </button>
                            ))}
                        </div>
                        {yearFilter.length === 0 && (
                            <span className="text-xs text-muted-foreground italic">All years</span>
                        )}
                    </div>
                    {filterOptions.voltageLevels.length > 0 && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Voltage:</span>
                            <div className="flex flex-wrap gap-1">
                                {filterOptions.voltageLevels.map(level => (
                                    <button
                                        key={level}
                                        onClick={() => toggleVoltageLevelFilter(level)}
                                        className={cn(
                                            "px-2 py-0.5 text-xs rounded-md transition-colors",
                                            voltageLevelFilter.includes(level)
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-muted hover:bg-muted/80 text-muted-foreground"
                                        )}
                                    >
                                        {level}
                                    </button>
                                ))}
                            </div>
                            {voltageLevelFilter.length > 0 && (
                                <button
                                    onClick={() => setVoltageLevelFilter([])}
                                    className="text-xs text-muted-foreground hover:text-foreground"
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                    )}
                </div>
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
                ) : filteredNetzentgelte.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b">
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Year</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">Voltage Level</th>
                                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">Leistung (€/kW)</th>
                                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">Arbeit (ct/kWh)</th>
                                    {isAdmin && <th className="text-right py-2 px-3 font-medium text-muted-foreground w-16"></th>}
                                </tr>
                            </thead>
                            <tbody>
                                {filteredNetzentgelte.map((item) => (
                                    <tr key={item.id} className="border-b border-border/50 hover:bg-muted/50">
                                        <td className="py-2 px-3">{item.year}</td>
                                        <td className="py-2 px-3">{item.voltage_level}</td>
                                        <td className="py-2 px-3 text-right font-mono">{item.leistung?.toFixed(2) || "-"}</td>
                                        <td className="py-2 px-3 text-right font-mono">{item.arbeit?.toFixed(3) || "-"}</td>
                                        {isAdmin && (
                                            <td className="py-2 px-3 text-right">
                                                <div className="relative inline-block" ref={openMenuId === `netz-${item.id}` ? menuRef : undefined}>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-7 w-7 p-0"
                                                        onClick={() => setOpenMenuId(openMenuId === `netz-${item.id}` ? null : `netz-${item.id}`)}
                                                    >
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                    {openMenuId === `netz-${item.id}` && (
                                                        <div className="absolute right-0 top-7 z-50 bg-popover border rounded-md shadow-md py-1 min-w-[100px]">
                                                            <button
                                                                className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2"
                                                                onClick={() => handleEditNetzentgelte(item)}
                                                            >
                                                                <Pencil className="h-3.5 w-3.5" /> Edit
                                                            </button>
                                                            <button
                                                                className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2 text-destructive"
                                                                onClick={() => {
                                                                    setOpenMenuId(null);
                                                                    handleDeleteNetzentgelte(item.id);
                                                                }}
                                                            >
                                                                <Trash2 className="h-3.5 w-3.5" /> Delete
                                                            </button>
                                                        </div>
                                                    )}
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
                ) : filteredHLZF.length > 0 ? (
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
                                    {isAdmin && <th className="text-right py-2 px-3 font-medium text-muted-foreground w-16"></th>}
                                </tr>
                            </thead>
                            <tbody>
                                {filteredHLZF.map((item) => (
                                    <tr key={item.id} className="border-b border-border/50 hover:bg-muted/50">
                                        <td className="py-2 px-3">{item.year}</td>
                                        <td className="py-2 px-3">{item.voltage_level}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.winter || "-"}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.fruehling || "-"}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.sommer || "-"}</td>
                                        <td className="py-2 px-3 font-mono whitespace-pre-line">{item.herbst || "-"}</td>
                                        {isAdmin && (
                                            <td className="py-2 px-3 text-right">
                                                <div className="relative inline-block" ref={openMenuId === `hlzf-${item.id}` ? menuRef : undefined}>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-7 w-7 p-0"
                                                        onClick={() => setOpenMenuId(openMenuId === `hlzf-${item.id}` ? null : `hlzf-${item.id}`)}
                                                    >
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                    {openMenuId === `hlzf-${item.id}` && (
                                                        <div className="absolute right-0 top-7 z-50 bg-popover border rounded-md shadow-md py-1 min-w-[100px]">
                                                            <button
                                                                className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2"
                                                                onClick={() => handleEditHLZF(item)}
                                                            >
                                                                <Pencil className="h-3.5 w-3.5" /> Edit
                                                            </button>
                                                            <button
                                                                className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2 text-destructive"
                                                                onClick={() => {
                                                                    setOpenMenuId(null);
                                                                    handleDeleteHLZF(item.id);
                                                                }}
                                                            >
                                                                <Trash2 className="h-3.5 w-3.5" /> Delete
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">No HLZF data available</p>
                )}
            </Card>

            {/* Downloaded Files */}
            {files.length > 0 && (
                <Card className="p-6">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <FileDown className="h-5 w-5 text-orange-500" />
                        Downloaded Files
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {files.map((file, idx) => (
                            <a
                                key={idx}
                                href={`http://localhost:8000${file.path}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                            >
                                <FileDown className="h-8 w-8 text-red-500" />
                                <div className="overflow-hidden">
                                    <p className="font-medium text-sm truncate">{file.name}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {(file.size / 1024).toFixed(0)} KB
                                    </p>
                                </div>
                            </a>
                        ))}
                    </div>
                </Card>
            )}

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

            {/* Edit Modal */}
            {editModalOpen && editRecord && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditModalOpen(false)}>
                    <div className="bg-background border rounded-lg shadow-lg p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                        <h3 className="text-lg font-semibold mb-4">
                            {editModalType === 'netzentgelte' ? 'Edit Netzentgelte' : 'Edit HLZF'}
                        </h3>

                        {editModalType === 'netzentgelte' ? (
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium mb-1">Leistung (€/kW)</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        className="w-full px-3 py-2 border rounded-md bg-background"
                                        value={editRecord.leistung ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, leistung: e.target.value ? parseFloat(e.target.value) : undefined })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Arbeit (ct/kWh)</label>
                                    <input
                                        type="number"
                                        step="0.001"
                                        className="w-full px-3 py-2 border rounded-md bg-background"
                                        value={editRecord.arbeit ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, arbeit: e.target.value ? parseFloat(e.target.value) : undefined })}
                                    />
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <p className="text-sm text-muted-foreground mb-2">Enter time ranges (comma-separated, e.g., "08:00 - 12:00, 17:00 - 19:00")</p>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Winter</label>
                                    <input
                                        type="text"
                                        className="w-full px-3 py-2 border rounded-md bg-background"
                                        value={editRecord.winter ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, winter: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Frühling</label>
                                    <input
                                        type="text"
                                        className="w-full px-3 py-2 border rounded-md bg-background"
                                        value={editRecord.fruehling ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, fruehling: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Sommer</label>
                                    <input
                                        type="text"
                                        className="w-full px-3 py-2 border rounded-md bg-background"
                                        value={editRecord.sommer ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, sommer: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Herbst</label>
                                    <input
                                        type="text"
                                        className="w-full px-3 py-2 border rounded-md bg-background"
                                        value={editRecord.herbst ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, herbst: e.target.value })}
                                    />
                                </div>
                            </div>
                        )}

                        <div className="flex justify-end gap-2 mt-6">
                            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                onClick={handleSaveEdit}
                                disabled={updateNetzentgelteMutation.isPending || updateHLZFMutation.isPending}
                            >
                                {(updateNetzentgelteMutation.isPending || updateHLZFMutation.isPending) ? (
                                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                ) : null}
                                Save
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
