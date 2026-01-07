import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
    ArrowLeft,
    Building,
    Database,
    ExternalLink,
    Globe,
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
    Check,
    ChevronDown,
    ChevronUp,
    Upload,
    Info,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/use-auth";
import { useState, useMemo, useRef, useEffect } from "react";
import { VerificationBadge } from "@/components/verification-badge";
import { ExtractionSourceBadge } from "@/components/extraction-source-badge";
import { SmartDropdown } from "@/components/SmartDropdown";

// Crawl configuration - matching SearchPage defaults
const AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022];
const DEFAULT_CRAWL_YEARS = [2025, 2024];

export function DNODetailPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { toast } = useToast();

    // Filter state - will be set dynamically based on available data
    const [yearFilter, setYearFilter] = useState<number[]>([]);
    const [yearFilterInitialized, setYearFilterInitialized] = useState(false);
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

    // Crawl dialog state
    const [crawlDialogOpen, setCrawlDialogOpen] = useState(false);
    const [crawlYears, setCrawlYears] = useState<number[]>(DEFAULT_CRAWL_YEARS);
    const [crawlDataType, setCrawlDataType] = useState<'all' | 'netzentgelte' | 'hlzf'>('all');
    const [crawlJobType, setCrawlJobType] = useState<'full' | 'crawl' | 'extract'>('full');
    const [showAdvancedCrawl, setShowAdvancedCrawl] = useState(false);

    // Edit DNO metadata dialog state
    const [editDNOOpen, setEditDNOOpen] = useState(false);
    const [editDNOData, setEditDNOData] = useState({
        name: '',
        region: '',
        website: '',
        description: '',
        phone: '',
        email: '',
        contact_address: '',
    });

    // Delete DNO dialog state
    const [deleteDNOOpen, setDeleteDNOOpen] = useState(false);

    // More details collapse state
    const [showMoreDetails, setShowMoreDetails] = useState(false);

    // Upload dialog state
    const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
    const [uploadResults, setUploadResults] = useState<Array<{
        filename: string;
        success: boolean;
        message: string;
        detected_type?: string | null;
        detected_year?: number | null;
    }>>([]);
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

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

    // Fetch DNO details first (works with both slug and numeric ID)
    const { data: dnoResponse, isLoading: dnoLoading, error: dnoError } = useQuery({
        queryKey: ["dno", id],
        queryFn: () => api.dnos.get(id!),
        enabled: !!id,
        staleTime: 0, // Always consider data stale
        refetchOnMount: 'always', // Always refetch when component mounts
    });

    // Get the numeric ID from the response (handles both slug and ID access)
    const numericId = dnoResponse?.data?.id;

    // Redirect slug URLs to numeric ID URLs for consistency
    useEffect(() => {
        if (numericId && id && !id.match(/^\d+$/) && numericId !== id) {
            // User accessed via slug, redirect to numeric ID
            navigate(`/dnos/${numericId}`, { replace: true });
        }
    }, [numericId, id, navigate]);

    // Fetch DNO crawl jobs (poll when active) - use numeric ID
    const { data: jobsResponse, isLoading: jobsLoading } = useQuery({
        queryKey: ["dno-jobs", numericId],
        queryFn: () => api.dnos.getJobs(numericId!, 20),
        enabled: !!numericId,
        staleTime: 0,
        refetchOnMount: 'always',
        refetchInterval: (query) => {
            // Poll every 3s while there are active jobs
            const jobs = query.state.data?.data || [];
            const hasActiveJobs = jobs.some((job: { status: string }) =>
                job.status === "pending" || job.status === "running"
            );
            return hasActiveJobs ? 3000 : false;
        },
    });

    // Check if there are active jobs (for data refresh)
    const hasActiveJobs = useMemo(() => {
        const jobs = jobsResponse?.data || [];
        return jobs.some((job: { status: string }) =>
            job.status === "pending" || job.status === "running"
        );
    }, [jobsResponse?.data]);

    // Fetch DNO data (netzentgelte, hlzf) - use numeric ID
    const { data: dataResponse, isLoading: dataLoading, refetch: refetchData } = useQuery({
        queryKey: ["dno-data", numericId],
        queryFn: () => api.dnos.getData(numericId!),
        enabled: !!numericId,
        staleTime: 0,
        refetchOnMount: 'always',
        refetchInterval: hasActiveJobs ? 5000 : false, // Poll every 5s while jobs are active
    });

    // Fetch available files - also refresh when jobs are active - use numeric ID
    const { data: filesResponse } = useQuery({
        queryKey: ["dno-files", numericId],
        queryFn: () => api.dnos.getFiles(numericId!),
        enabled: !!numericId,
        staleTime: 0,
        refetchOnMount: 'always',
        refetchInterval: hasActiveJobs ? 5000 : false,
    });

    const triggerCrawlMutation = useMutation({
        mutationFn: async ({ years, dataType, jobType }: { 
            years: number[]; 
            dataType: 'all' | 'netzentgelte' | 'hlzf';
            jobType: 'full' | 'crawl' | 'extract';
        }) => {
            // When 'all' is selected, create separate jobs for netzentgelte and hlzf
            const typesToCrawl = dataType === 'all' ? ['netzentgelte', 'hlzf'] as const : [dataType];
            const results = [];

            for (const year of years) {
                for (const type of typesToCrawl) {
                    const result = await api.dnos.triggerCrawl(numericId!, { 
                        year, 
                        data_type: type,
                        job_type: jobType,
                    });
                    results.push(result);
                }
            }
            return results;
        },
        onSuccess: (results, variables) => {
            const jobCount = results.length;
            const jobTypeLabel = variables.jobType === 'full' ? 'Full' : 
                                 variables.jobType === 'crawl' ? 'Crawl' : 'Extract';
            toast({
                title: `${jobTypeLabel} job${jobCount > 1 ? 's' : ''} triggered`,
                description: `${jobCount} job${jobCount > 1 ? 's' : ''} queued for years: ${variables.years.join(', ')}`,
            });
            queryClient.invalidateQueries({ queryKey: ["dno-jobs", numericId] });
            setCrawlDialogOpen(false);
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

    // Calculate total job count based on years and data type selection
    const crawlJobCount = crawlYears.length * (crawlDataType === 'all' ? 2 : 1);

    // Toggle year in crawl selection
    const toggleCrawlYear = (year: number) => {
        setCrawlYears((prev) => {
            if (prev.includes(year)) {
                if (prev.length === 1) return prev; // keep at least one
                return prev.filter((y) => y !== year);
            }
            return [...prev, year].sort((a, b) => b - a);
        });
    };

    // Handle file upload
    const handleFileUpload = async (files: FileList | null) => {
        if (!files || files.length === 0 || !numericId) return;

        setIsUploading(true);
        setUploadResults([]);

        const results: typeof uploadResults = [];

        for (const file of Array.from(files)) {
            try {
                const response = await api.dnos.uploadFile(numericId, file);
                if (response.success) {
                    results.push({
                        filename: file.name,
                        success: true,
                        message: `Saved as ${response.data.filename}`,
                        detected_type: response.data.detected_type,
                        detected_year: response.data.detected_year,
                    });
                } else {
                    results.push({
                        filename: file.name,
                        success: false,
                        message: response.message || response.data?.hint || 'Detection failed',
                    });
                }
            } catch {
                results.push({
                    filename: file.name,
                    success: false,
                    message: 'Upload failed',
                });
            }
        }

        setUploadResults(results);
        setIsUploading(false);

        // Refresh files list
        queryClient.invalidateQueries({ queryKey: ["dno-files", numericId] });
        queryClient.invalidateQueries({ queryKey: ["dno", numericId] });

        // Show toast for results
        const successCount = results.filter(r => r.success).length;
        if (successCount > 0) {
            toast({
                title: "Files Uploaded",
                description: `${successCount} of ${results.length} file(s) uploaded successfully`,
            });
        }
    };

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

    // Set initial year filter based on available data
    // Priority: 2024 if available, otherwise latest year, or only year if just one
    useEffect(() => {
        if (yearFilterInitialized || filterOptions.years.length === 0) return;
        
        const availableYears = filterOptions.years;
        let defaultYear: number;
        
        if (availableYears.includes(2024)) {
            // Prefer 2024 if available
            defaultYear = 2024;
        } else if (availableYears.length === 1) {
            // Only one year available, use it
            defaultYear = availableYears[0];
        } else {
            // Use the latest year (array is sorted desc)
            defaultYear = availableYears[0];
        }
        
        setYearFilter([defaultYear]);
        setYearFilterInitialized(true);
    }, [filterOptions.years, yearFilterInitialized]);

    // Calculate data completeness
    // Expected: 5 voltage levels × 2 data types × 5 years (2022-2026) = 50 rows total
    const dataCompleteness = useMemo(() => {
        const netzentgelteCount = dnoData?.netzentgelte?.length || 0;
        const hlzfCount = dnoData?.hlzf?.length || 0;
        const totalRecords = netzentgelteCount + hlzfCount;
        const expectedRecords = 50; // 5 voltage levels × 5 years × 2 data types
        const percentage = expectedRecords > 0 ? Math.min((totalRecords / expectedRecords) * 100, 100) : 0;
        return {
            total: totalRecords,
            expected: expectedRecords,
            percentage: percentage,
        };
    }, [dnoData?.netzentgelte?.length, dnoData?.hlzf?.length]);

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
        mutationFn: (recordId: number) => api.dnos.deleteNetzentgelte(numericId!, recordId),
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
        mutationFn: (recordId: number) => api.dnos.deleteHLZF(numericId!, recordId),
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
            api.dnos.updateNetzentgelte(numericId!, data.id, { leistung: data.leistung, arbeit: data.arbeit }),
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
            api.dnos.updateHLZF(numericId!, data.id, { winter: data.winter, fruehling: data.fruehling, sommer: data.sommer, herbst: data.herbst }),
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

    // Update DNO metadata mutation
    const updateDNOMutation = useMutation({
        mutationFn: (data: { name?: string; region?: string; website?: string; description?: string }) =>
            api.dnos.updateDNO(numericId!, data),
        onSuccess: () => {
            toast({ title: "DNO updated", description: "Metadata saved successfully" });
            setEditDNOOpen(false);
            queryClient.invalidateQueries({ queryKey: ["dno", numericId] });
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to update DNO", description: message });
        },
    });

    // Delete DNO mutation
    const deleteDNOMutation = useMutation({
        mutationFn: () => api.dnos.deleteDNO(numericId!),
        onSuccess: () => {
            toast({ title: "DNO deleted", description: "DNO and all associated data have been permanently deleted" });
            setDeleteDNOOpen(false);
            queryClient.invalidateQueries({ queryKey: ["dnos"] });
            navigate("/dnos");
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to delete DNO", description: message });
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
                    {isAdmin() && (
                        <Button
                            variant="outline"
                            className="border-destructive text-destructive hover:bg-destructive/10"
                            onClick={() => setDeleteDNOOpen(true)}
                        >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                        </Button>
                    )}
                    {isAdmin() && (
                        <Button
                            variant="outline"
                            onClick={() => {
                                setEditDNOData({
                                    name: dno.name || '',
                                    region: dno.region || '',
                                    website: dno.website || '',
                                    description: dno.description || '',
                                    phone: dno.phone || '',
                                    email: dno.email || '',
                                    contact_address: dno.contact_address || '',
                                });
                                setEditDNOOpen(true);
                            }}
                        >
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                        </Button>
                    )}
                    <Dialog open={crawlDialogOpen} onOpenChange={setCrawlDialogOpen}>
                        <DialogTrigger asChild>
                            <Button disabled={dno.crawlable === false && !dno.has_local_files}>
                                <RefreshCw className="mr-2 h-4 w-4" />
                                Trigger Crawl
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-md">
                            <DialogHeader>
                                <DialogTitle>Trigger Crawl for {dno.name}</DialogTitle>
                                <DialogDescription>
                                    Select years and data types to crawl. One job will be created per year.
                                </DialogDescription>
                            </DialogHeader>

                            {/* Year Selection */}
                            <div className="space-y-3">
                                <label className="text-sm font-medium">Years to crawl</label>
                                <div className="flex flex-wrap gap-2">
                                    {AVAILABLE_YEARS.map((year) => {
                                        const isSelected = crawlYears.includes(year);
                                        return (
                                            <button
                                                key={year}
                                                type="button"
                                                onClick={() => toggleCrawlYear(year)}
                                                className={cn(
                                                    "flex items-center gap-2 px-3 py-2 rounded-md border text-sm font-medium transition-colors",
                                                    isSelected
                                                        ? "bg-primary text-primary-foreground border-primary"
                                                        : "bg-background border-input hover:bg-muted"
                                                )}
                                            >
                                                <div className={cn(
                                                    "w-4 h-4 rounded border flex items-center justify-center",
                                                    isSelected
                                                        ? "bg-primary-foreground/20 border-primary-foreground/50"
                                                        : "border-current opacity-50"
                                                )}>
                                                    {isSelected && <Check className="w-3 h-3" />}
                                                </div>
                                                {year}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Advanced Options (Collapsible) */}
                            <div className="border rounded-lg overflow-hidden">
                                <button
                                    type="button"
                                    onClick={() => setShowAdvancedCrawl(!showAdvancedCrawl)}
                                    className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-sm"
                                >
                                    <span className="font-medium">Advanced Options</span>
                                    {showAdvancedCrawl ? (
                                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                                    ) : (
                                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                    )}
                                </button>
                                {showAdvancedCrawl && (
                                    <div className="p-3 border-t space-y-4">
                                        {/* Job Type Selection */}
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium">Job Type</label>
                                            <div className="flex flex-wrap gap-2">
                                                {([
                                                    { value: 'full', label: 'Full Pipeline', desc: 'Crawl + Extract' },
                                                    { value: 'crawl', label: 'Crawl Only', desc: 'Download file' },
                                                    { value: 'extract', label: 'Extract Only', desc: 'Process existing file' },
                                                ] as const).map((opt) => (
                                                    <button
                                                        key={opt.value}
                                                        type="button"
                                                        onClick={() => setCrawlJobType(opt.value)}
                                                        className={cn(
                                                            "flex flex-col items-start px-3 py-2 rounded-md border text-sm transition-colors",
                                                            crawlJobType === opt.value
                                                                ? "bg-primary text-primary-foreground border-primary"
                                                                : "bg-background border-input hover:bg-muted"
                                                        )}
                                                    >
                                                        <span className="font-medium">{opt.label}</span>
                                                        <span className={cn(
                                                            "text-xs",
                                                            crawlJobType === opt.value 
                                                                ? "text-primary-foreground/70" 
                                                                : "text-muted-foreground"
                                                        )}>{opt.desc}</span>
                                                    </button>
                                                ))}
                                            </div>
                                            {crawlJobType === 'extract' && (
                                                <p className="text-xs text-muted-foreground flex items-center gap-1">
                                                    <Info className="w-3 h-3" />
                                                    Requires an existing downloaded file for the selected year/type
                                                </p>
                                            )}
                                        </div>
                                        
                                        {/* Data Type Selection */}
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium">Data Type</label>
                                            <div className="flex gap-2">
                                                {(['all', 'netzentgelte', 'hlzf'] as const).map((type) => (
                                                    <button
                                                        key={type}
                                                        type="button"
                                                        onClick={() => setCrawlDataType(type)}
                                                        className={cn(
                                                            "px-3 py-1.5 rounded-md border text-sm font-medium transition-colors",
                                                            crawlDataType === type
                                                                ? "bg-primary text-primary-foreground border-primary"
                                                                : "bg-background border-input hover:bg-muted"
                                                        )}
                                                    >
                                                        {type === 'all' ? 'All' : type === 'netzentgelte' ? 'Netzentgelte' : 'HLZF'}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>

                            <DialogFooter className="gap-2 sm:gap-0">
                                <Button
                                    variant="outline"
                                    onClick={() => setCrawlDialogOpen(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    onClick={() => triggerCrawlMutation.mutate({ 
                                        years: crawlYears, 
                                        dataType: crawlDataType,
                                        jobType: crawlJobType,
                                    })}
                                    disabled={triggerCrawlMutation.isPending || crawlYears.length === 0}
                                >
                                    {triggerCrawlMutation.isPending ? (
                                        <>
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Creating jobs...
                                        </>
                                    ) : (
                                        <>
                                            Start {crawlJobCount} {crawlJobType === 'full' ? '' : crawlJobType + ' '}Job{crawlJobCount > 1 ? 's' : ''}
                                        </>
                                    )}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    {/* Show crawlability warning */}
                    {dno.crawlable === false && (
                        <Badge variant="outline" className="bg-amber-500/10 text-amber-600 border-amber-500/20">
                            <AlertCircle className="mr-1 h-3 w-3" />
                            {dno.crawl_blocked_reason === 'cloudflare' ? 'Cloudflare Protected' :
                                dno.crawl_blocked_reason === 'robots_disallow_all' ? 'Blocked by robots.txt' :
                                    dno.crawl_blocked_reason || 'Not Crawlable'}
                            {dno.has_local_files && ' (Local files available)'}
                        </Badge>
                    )}

                    {/* Edit DNO Dialog - Admin Only */}
                    {isAdmin() && (
                        <Dialog open={editDNOOpen} onOpenChange={setEditDNOOpen}>
                            <DialogContent className="sm:max-w-md">
                                <DialogHeader>
                                    <DialogTitle>Edit DNO</DialogTitle>
                                    <DialogDescription>
                                        Update metadata for {dno.name}
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="grid gap-4 py-4">
                                    <div className="grid gap-2">
                                        <label className="text-sm font-medium">Name</label>
                                        <Input
                                            type="text"
                                            value={editDNOData.name}
                                            onChange={(e) => setEditDNOData(prev => ({ ...prev, name: e.target.value }))}
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <label className="text-sm font-medium">Region</label>
                                        <Input
                                            type="text"
                                            value={editDNOData.region}
                                            onChange={(e) => setEditDNOData(prev => ({ ...prev, region: e.target.value }))}
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <label className="text-sm font-medium">Website</label>
                                        <Input
                                            type="url"
                                            value={editDNOData.website}
                                            onChange={(e) => setEditDNOData(prev => ({ ...prev, website: e.target.value }))}
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <label className="text-sm font-medium">Description</label>
                                        <Input
                                            type="text"
                                            value={editDNOData.description}
                                            onChange={(e) => setEditDNOData(prev => ({ ...prev, description: e.target.value }))}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="grid gap-2">
                                            <label className="text-sm font-medium">Phone</label>
                                            <Input
                                                type="text"
                                                value={editDNOData.phone}
                                                onChange={(e) => setEditDNOData(prev => ({ ...prev, phone: e.target.value }))}
                                            />
                                        </div>
                                        <div className="grid gap-2">
                                            <label className="text-sm font-medium">Email</label>
                                            <Input
                                                type="email"
                                                value={editDNOData.email}
                                                onChange={(e) => setEditDNOData(prev => ({ ...prev, email: e.target.value }))}
                                            />
                                        </div>
                                    </div>
                                    <div className="grid gap-2">
                                        <label className="text-sm font-medium">Contact Address</label>
                                        <Input
                                            type="text"
                                            value={editDNOData.contact_address}
                                            onChange={(e) => setEditDNOData(prev => ({ ...prev, contact_address: e.target.value }))}
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setEditDNOOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        onClick={() => updateDNOMutation.mutate(editDNOData)}
                                        disabled={updateDNOMutation.isPending}
                                    >
                                        {updateDNOMutation.isPending ? (
                                            <>
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                Saving...
                                            </>
                                        ) : (
                                            "Save Changes"
                                        )}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    )}

                    {/* Delete DNO Dialog - Admin Only */}
                    {isAdmin() && (
                        <Dialog open={deleteDNOOpen} onOpenChange={setDeleteDNOOpen}>
                            <DialogContent className="sm:max-w-md">
                                <DialogHeader>
                                    <DialogTitle className="text-destructive">Delete DNO</DialogTitle>
                                    <DialogDescription>
                                        Are you sure you want to permanently delete <strong>{dno.name}</strong>?
                                        This will also delete all associated Netzentgelte, HLZF data, and crawl jobs.
                                        This action cannot be undone.
                                    </DialogDescription>
                                </DialogHeader>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setDeleteDNOOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        variant="destructive"
                                        onClick={() => deleteDNOMutation.mutate()}
                                        disabled={deleteDNOMutation.isPending}
                                    >
                                        {deleteDNOMutation.isPending ? (
                                            <>
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                Deleting...
                                            </>
                                        ) : (
                                            <>
                                                <Trash2 className="mr-2 h-4 w-4" />
                                                Delete Permanently
                                            </>
                                        )}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    )}
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
                        <div className="relative">
                            <svg className="h-12 w-12 -rotate-90" viewBox="0 0 36 36">
                                <circle
                                    cx="18"
                                    cy="18"
                                    r="15.5"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                    className="text-muted/30"
                                />
                                <circle
                                    cx="18"
                                    cy="18"
                                    r="15.5"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                    strokeDasharray={`${dataCompleteness.percentage} 100`}
                                    strokeLinecap="round"
                                    className={cn(
                                        dataCompleteness.percentage >= 80 ? "text-green-500" :
                                            dataCompleteness.percentage >= 50 ? "text-yellow-500" :
                                                "text-red-500"
                                    )}
                                />
                            </svg>
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">Data Completeness</p>
                            <p className="text-2xl font-bold">{dataCompleteness.percentage.toFixed(0)}%</p>
                        </div>
                    </div>
                </Card>
            </div>

            {/* DNO Details */}
            <Card className="p-4">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-muted-foreground">Details</h2>
                    {/* Enrichment Status Badge */}
                    {dno.enrichment_status && dno.enrichment_status !== 'completed' && (
                        <Badge variant={dno.enrichment_status === 'processing' ? 'default' : 'outline'} className="text-xs">
                            {dno.enrichment_status === 'processing' && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                            {dno.enrichment_status === 'pending' ? 'Enrichment Pending' :
                             dno.enrichment_status === 'processing' ? 'Enriching...' :
                             dno.enrichment_status === 'failed' ? 'Enrichment Failed' : ''}
                        </Badge>
                    )}
                </div>
                
                {/* Primary Info - Always Visible */}
                <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2 text-sm">
                    <div className="flex justify-between sm:block">
                        <dt className="text-muted-foreground inline sm:inline-block sm:w-20">Slug</dt>
                        <dd className="font-mono inline">{dno.slug}</dd>
                    </div>
                    {dno.official_name && (
                        <div className="flex justify-between sm:block">
                            <dt className="text-muted-foreground inline sm:inline-block sm:w-20">Official</dt>
                            <dd className="inline">{dno.official_name}</dd>
                        </div>
                    )}
                    {dno.website && (
                        <div className="flex justify-between sm:block">
                            <dt className="text-muted-foreground inline sm:inline-block sm:w-20">Website</dt>
                            <dd className="inline">
                                <a href={dno.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                                    {new URL(dno.website).hostname}
                                </a>
                            </dd>
                        </div>
                    )}
                    {dno.contact_address && (
                        <div className="flex justify-between sm:block sm:col-span-2">
                            <dt className="text-muted-foreground inline sm:inline-block sm:w-20">Address</dt>
                            <dd className="inline">{dno.contact_address}</dd>
                        </div>
                    )}
                </dl>

                {/* More Details Button */}
                <button
                    onClick={() => setShowMoreDetails(!showMoreDetails)}
                    className="flex items-center gap-2 mt-4 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                    <Info className="h-4 w-4" />
                    <span>{showMoreDetails ? 'Hide Details' : 'More Details'}</span>
                    {showMoreDetails ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>

                {/* Collapsible More Details Section */}
                {showMoreDetails && (
                    <div className="mt-4 pt-4 border-t border-border space-y-4">
                        {/* Source Availability Badges */}
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs text-muted-foreground">Data Sources:</span>
                            <Badge variant={dno.has_mastr ? 'default' : 'outline'} className={cn("text-xs", dno.has_mastr && "bg-blue-500")}>
                                MaStR {dno.has_mastr ? '✓' : '–'}
                            </Badge>
                            <Badge variant={dno.has_vnb ? 'default' : 'outline'} className={cn("text-xs", dno.has_vnb && "bg-green-500")}>
                                VNB Digital {dno.has_vnb ? '✓' : '–'}
                            </Badge>
                            <Badge variant={dno.has_bdew ? 'default' : 'outline'} className={cn("text-xs", dno.has_bdew && "bg-purple-500")}>
                                BDEW {dno.has_bdew ? '✓' : '–'}
                            </Badge>
                        </div>

                        {/* MaStR Data Section */}
                        {dno.mastr_data && (
                            <div className="rounded-lg border border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/20 p-3">
                                <h4 className="text-xs font-semibold text-blue-700 dark:text-blue-300 mb-2 flex items-center gap-1">
                                    <Database className="h-3 w-3" /> MaStR (Marktstammdatenregister)
                                </h4>
                                <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm">
                                    <div className="flex justify-between sm:block">
                                        <dt className="text-muted-foreground inline sm:inline-block sm:w-24">MaStR Nr.</dt>
                                        <dd className="font-mono inline text-xs">{dno.mastr_data.mastr_nr}</dd>
                                    </div>
                                    {dno.mastr_data.acer_code && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">ACER Code</dt>
                                            <dd className="font-mono inline text-xs">{dno.mastr_data.acer_code}</dd>
                                        </div>
                                    )}
                                    {dno.mastr_data.region && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Region</dt>
                                            <dd className="inline text-xs">{dno.mastr_data.region}</dd>
                                        </div>
                                    )}
                                    {dno.mastr_data.marktrollen && dno.mastr_data.marktrollen.length > 0 && (
                                        <div className="flex justify-between sm:block sm:col-span-full">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Market Roles</dt>
                                            <dd className="inline">
                                                <div className="flex flex-wrap gap-1 mt-1 sm:mt-0 sm:inline-flex">
                                                    {dno.mastr_data.marktrollen.map((role, idx) => (
                                                        <Badge key={idx} variant="outline" className="text-xs">{role}</Badge>
                                                    ))}
                                                </div>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.mastr_data.is_active !== undefined && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Status</dt>
                                            <dd className="inline">
                                                <Badge variant={dno.mastr_data.is_active ? 'default' : 'secondary'} className="text-xs">
                                                    {dno.mastr_data.is_active ? 'Active' : 'Inactive'}
                                                </Badge>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.mastr_data.closed_network && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Network</dt>
                                            <dd className="inline">
                                                <Badge variant="outline" className="text-xs">Closed Network</Badge>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.mastr_data.registration_date && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Registered</dt>
                                            <dd className="inline text-xs">{new Date(dno.mastr_data.registration_date).toLocaleDateString('de-DE')}</dd>
                                        </div>
                                    )}
                                    {dno.mastr_data.contact_address && (
                                        <div className="flex justify-between sm:block sm:col-span-full">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Address</dt>
                                            <dd className="inline text-xs">{dno.mastr_data.contact_address}</dd>
                                        </div>
                                    )}
                                </dl>
                            </div>
                        )}

                        {/* VNB Digital Data Section */}
                        {dno.vnb_data && (
                            <div className="rounded-lg border border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/20 p-3">
                                <h4 className="text-xs font-semibold text-green-700 dark:text-green-300 mb-2 flex items-center gap-1">
                                    <Globe className="h-3 w-3" /> VNB Digital
                                </h4>
                                <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm">
                                    <div className="flex justify-between sm:block">
                                        <dt className="text-muted-foreground inline sm:inline-block sm:w-24">VNB ID</dt>
                                        <dd className="font-mono inline text-xs">{dno.vnb_data.vnb_id}</dd>
                                    </div>
                                    {dno.vnb_data.official_name && (
                                        <div className="flex justify-between sm:block sm:col-span-2">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Official Name</dt>
                                            <dd className="inline text-xs">{dno.vnb_data.official_name}</dd>
                                        </div>
                                    )}
                                    {dno.vnb_data.homepage_url && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Website</dt>
                                            <dd className="inline">
                                                <a href={dno.vnb_data.homepage_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline text-xs">
                                                    {new URL(dno.vnb_data.homepage_url).hostname}
                                                </a>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.vnb_data.phone && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Phone</dt>
                                            <dd className="inline">
                                                <a href={`tel:${dno.vnb_data.phone}`} className="text-primary hover:underline text-xs">{dno.vnb_data.phone}</a>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.vnb_data.email && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Email</dt>
                                            <dd className="inline">
                                                <a href={`mailto:${dno.vnb_data.email}`} className="text-primary hover:underline text-xs">{dno.vnb_data.email}</a>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.vnb_data.address && (
                                        <div className="flex justify-between sm:block sm:col-span-full">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Address</dt>
                                            <dd className="inline text-xs">{dno.vnb_data.address}</dd>
                                        </div>
                                    )}
                                    {dno.vnb_data.types && dno.vnb_data.types.length > 0 && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Types</dt>
                                            <dd className="inline">
                                                <div className="flex flex-wrap gap-1 mt-1 sm:mt-0 sm:inline-flex">
                                                    {dno.vnb_data.types.map((t, idx) => (
                                                        <Badge key={idx} variant="outline" className="text-xs">{t}</Badge>
                                                    ))}
                                                </div>
                                            </dd>
                                        </div>
                                    )}
                                    {dno.vnb_data.voltage_types && dno.vnb_data.voltage_types.length > 0 && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Voltage</dt>
                                            <dd className="inline">
                                                <div className="flex flex-wrap gap-1 mt-1 sm:mt-0 sm:inline-flex">
                                                    {dno.vnb_data.voltage_types.map((v, idx) => (
                                                        <Badge key={idx} variant="outline" className="text-xs">{v}</Badge>
                                                    ))}
                                                </div>
                                            </dd>
                                        </div>
                                    )}
                                </dl>
                            </div>
                        )}

                        {/* BDEW Data Section */}
                        {dno.bdew_data && dno.bdew_data.length > 0 && (
                            <div className="rounded-lg border border-purple-200 bg-purple-50/50 dark:border-purple-800 dark:bg-purple-950/20 p-3">
                                <h4 className="text-xs font-semibold text-purple-700 dark:text-purple-300 mb-2 flex items-center gap-1">
                                    <Building className="h-3 w-3" /> BDEW Codes ({dno.bdew_data.length})
                                </h4>
                                <div className="space-y-3">
                                    {dno.bdew_data.map((bdew, idx) => (
                                        <dl key={idx} className={cn(
                                            "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm",
                                            idx > 0 && "pt-3 border-t border-purple-200 dark:border-purple-800"
                                        )}>
                                            <div className="flex justify-between sm:block">
                                                <dt className="text-muted-foreground inline sm:inline-block sm:w-24">BDEW Code</dt>
                                                <dd className="font-mono inline text-xs">{bdew.bdew_code}</dd>
                                            </div>
                                            {bdew.market_function && (
                                                <div className="flex justify-between sm:block">
                                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Market Role</dt>
                                                    <dd className="inline">
                                                        <Badge variant="outline" className={cn(
                                                            "text-xs",
                                                            bdew.market_function === 'Netzbetreiber' && "border-purple-400 text-purple-700 dark:text-purple-300"
                                                        )}>
                                                            {bdew.market_function}
                                                        </Badge>
                                                    </dd>
                                                </div>
                                            )}
                                            {bdew.is_grid_operator && (
                                                <div className="flex justify-between sm:block">
                                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Grid Op.</dt>
                                                    <dd className="inline">
                                                        <Badge variant="default" className="text-xs bg-purple-500">Grid Operator</Badge>
                                                    </dd>
                                                </div>
                                            )}
                                            {bdew.contact_email && (
                                                <div className="flex justify-between sm:block">
                                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Email</dt>
                                                    <dd className="inline">
                                                        <a href={`mailto:${bdew.contact_email}`} className="text-primary hover:underline text-xs">{bdew.contact_email}</a>
                                                    </dd>
                                                </div>
                                            )}
                                            {bdew.contact_phone && (
                                                <div className="flex justify-between sm:block">
                                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Phone</dt>
                                                    <dd className="inline">
                                                        <a href={`tel:${bdew.contact_phone}`} className="text-primary hover:underline text-xs">{bdew.contact_phone}</a>
                                                    </dd>
                                                </div>
                                            )}
                                            {(bdew.street || bdew.city) && (
                                                <div className="flex justify-between sm:block sm:col-span-full">
                                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Address</dt>
                                                    <dd className="inline text-xs">
                                                        {[bdew.street, bdew.zip_code, bdew.city].filter(Boolean).join(', ')}
                                                    </dd>
                                                </div>
                                            )}
                                        </dl>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* General Info Section */}
                        <div className="rounded-lg border border-border p-3">
                            <h4 className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
                                <Info className="h-3 w-3" /> General
                            </h4>
                            <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm">
                                {/* Crawlability */}
                                <div className="flex justify-between sm:block">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Crawlable</dt>
                                    <dd className="inline">
                                        {dno.crawlable ? (
                                            <Badge variant="default" className="text-xs bg-green-500">
                                                <CheckCircle className="h-3 w-3 mr-1" /> Yes
                                            </Badge>
                                        ) : (
                                            <Badge variant="destructive" className="text-xs">
                                                <XCircle className="h-3 w-3 mr-1" /> No
                                                {dno.crawl_blocked_reason && ` (${dno.crawl_blocked_reason})`}
                                            </Badge>
                                        )}
                                    </dd>
                                </div>
                                
                                {/* Source & Timestamps */}
                                {dno.source && (
                                    <div className="flex justify-between sm:block">
                                        <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Source</dt>
                                        <dd className="inline">
                                            <Badge variant="outline" className="text-xs">{dno.source}</Badge>
                                        </dd>
                                    </div>
                                )}
                                {dno.created_at && (
                                    <div className="flex justify-between sm:block">
                                        <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Created</dt>
                                        <dd className="inline text-xs">{new Date(dno.created_at).toLocaleString('de-DE')}</dd>
                                    </div>
                                )}
                                {dno.updated_at && (
                                    <div className="flex justify-between sm:block">
                                        <dt className="text-muted-foreground inline sm:inline-block sm:w-24">Updated</dt>
                                        <dd className="inline text-xs">{new Date(dno.updated_at).toLocaleString('de-DE')}</dd>
                                    </div>
                                )}
                            </dl>
                        </div>
                    </div>
                )}
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
            <Card className="p-6 min-h-[320px]">
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
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" rowSpan={2}>Year</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" rowSpan={2}>Voltage Level</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50" colSpan={2}>{"≥ 2.500 h/a"}</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50" colSpan={2}>{"< 2.500 h/a"}</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50" rowSpan={2}>Status</th>
                                    {isAdmin() && <th className="text-right py-2 px-3 font-medium text-muted-foreground w-16" rowSpan={2}></th>}
                                </tr>
                                <tr className="border-b text-xs">
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground border-l border-border/50">Leistung (€/kW)</th>
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground">Arbeit (ct/kWh)</th>
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground border-l border-border/50">Leistung (€/kW)</th>
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground">Arbeit (ct/kWh)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredNetzentgelte.map((item) => (
                                    <tr key={item.id} className="border-b border-border/50 hover:bg-muted/50">
                                        <td className="py-2 px-3">{item.year}</td>
                                        <td className="py-2 px-3 font-medium">{item.voltage_level}</td>
                                        <td className="py-2 px-3 text-right font-mono border-l border-border/50">
                                            <span className="select-all">{item.leistung?.toFixed(2) || "-"}</span>
                                        </td>
                                        <td className="py-2 px-3 text-right font-mono">
                                            <span className="select-all">{item.arbeit?.toFixed(3) || "-"}</span>
                                        </td>
                                        <td className="py-2 px-3 text-right font-mono border-l border-border/50">
                                            <span className="select-all">{item.leistung_unter_2500h?.toFixed(2) || item.leistung?.toFixed(2) || "-"}</span>
                                        </td>
                                        <td className="py-2 px-3 text-right font-mono">
                                            <span className="select-all">{item.arbeit_unter_2500h?.toFixed(3) || item.arbeit?.toFixed(3) || "-"}</span>
                                        </td>
                                        <td className="py-2 px-3 text-center">
                                            <div className="flex items-center justify-center gap-1">
                                                <ExtractionSourceBadge
                                                    source={item.extraction_source}
                                                    model={item.extraction_model}
                                                    sourceFormat={item.extraction_source_format}
                                                    lastEditedBy={item.last_edited_by}
                                                    lastEditedAt={item.last_edited_at}
                                                    compact
                                                />
                                                <VerificationBadge
                                                    status={item.verification_status || "unverified"}
                                                    verifiedBy={item.verified_by}
                                                    verifiedAt={item.verified_at}
                                                    flaggedBy={item.flagged_by}
                                                    flaggedAt={item.flagged_at}
                                                    flagReason={item.flag_reason}
                                                    recordId={item.id}
                                                    recordType="netzentgelte"
                                                    dnoId={numericId!}
                                                    compact
                                                />
                                            </div>
                                        </td>
                                        {isAdmin() && (
                                            <td className="py-2 px-3 text-right">
                                                <SmartDropdown
                                                    trigger={
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-7 w-7 p-0"
                                                        >
                                                            <MoreVertical className="h-4 w-4" />
                                                        </Button>
                                                    }
                                                    isOpen={openMenuId === `netz-${item.id}`}
                                                    onOpenChange={(isOpen) => setOpenMenuId(isOpen ? `netz-${item.id}` : null)}
                                                    className="bg-popover border rounded-md shadow-md py-1"
                                                >
                                                    <button
                                                        className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2"
                                                        onClick={() => {
                                                            setOpenMenuId(null);
                                                            handleEditNetzentgelte(item);
                                                        }}
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
                                                </SmartDropdown>
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
            <Card className="p-6 min-h-[320px]">
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
                        <table className="w-full text-sm table-fixed">
                            <thead>
                                <tr className="border-b">
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground w-16">Year</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground w-20">Voltage Level</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Winter</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Frühling</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Sommer</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Herbst</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground w-24">Status</th>
                                    {isAdmin() && <th className="text-right py-2 px-3 font-medium text-muted-foreground w-12"></th>}
                                </tr>
                            </thead>
                            <tbody>
                                {filteredHLZF.map((item) => {
                                    // Selectable time component
                                    const SelectableTime = ({ value }: { value: string }) => {
                                        const handleClick = (e: React.MouseEvent<HTMLSpanElement>) => {
                                            e.stopPropagation();
                                            e.preventDefault();
                                            const selection = window.getSelection();
                                            const range = document.createRange();
                                            range.selectNodeContents(e.currentTarget);
                                            selection?.removeAllRanges();
                                            selection?.addRange(range);
                                        };
                                        return (
                                            <span
                                                className="cursor-text hover:bg-primary/20 rounded px-0.5"
                                                onClick={handleClick}
                                                onMouseDown={(e) => e.stopPropagation()}
                                                style={{ userSelect: 'text' }}
                                            >
                                                {value}
                                            </span>
                                        );
                                    };

                                    // Render time ranges from parsed backend array
                                    const renderTimeRanges = (
                                        ranges: { start: string; end: string }[] | null | undefined,
                                        rawValue: string | null | undefined
                                    ): React.ReactNode => {
                                        // Use parsed ranges if available
                                        if (ranges && ranges.length > 0) {
                                            return (
                                                <div className="space-y-0.5" style={{ userSelect: 'none' }}>
                                                    {ranges.map((range, idx) => (
                                                        <div key={idx} className="text-sm whitespace-nowrap flex items-center">
                                                            <SelectableTime value={range.start} />
                                                            <span className="text-muted-foreground px-1" style={{ userSelect: 'none' }}>–</span>
                                                            <SelectableTime value={range.end} />
                                                        </div>
                                                    ))}
                                                </div>
                                            );
                                        }

                                        // Fallback: show raw value or dash
                                        if (!rawValue || rawValue === "-" || rawValue.toLowerCase() === "entfällt") {
                                            return <span className="text-muted-foreground">-</span>;
                                        }

                                        return <span className="text-sm">{rawValue}</span>;
                                    };

                                    return (
                                        <tr key={item.id} className="border-b border-border/50 hover:bg-muted/50">
                                            <td className="py-2 px-3">{item.year}</td>
                                            <td className="py-2 px-3 font-medium">{item.voltage_level}</td>
                                            <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.winter_ranges, item.winter)}</td>
                                            <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.fruehling_ranges, item.fruehling)}</td>
                                            <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.sommer_ranges, item.sommer)}</td>
                                            <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.herbst_ranges, item.herbst)}</td>
                                            <td className="py-2 px-3 text-center">
                                                <div className="flex items-center justify-center gap-1">
                                                    <ExtractionSourceBadge
                                                        source={item.extraction_source}
                                                        model={item.extraction_model}
                                                        sourceFormat={item.extraction_source_format}
                                                        lastEditedBy={item.last_edited_by}
                                                        lastEditedAt={item.last_edited_at}
                                                        compact
                                                    />
                                                    <VerificationBadge
                                                        status={item.verification_status || "unverified"}
                                                        verifiedBy={item.verified_by}
                                                        verifiedAt={item.verified_at}
                                                        flaggedBy={item.flagged_by}
                                                        flaggedAt={item.flagged_at}
                                                        flagReason={item.flag_reason}
                                                        recordId={item.id}
                                                        recordType="hlzf"
                                                        dnoId={numericId!}
                                                        compact
                                                    />
                                                </div>
                                            </td>
                                            {isAdmin() && (
                                                <td className="py-2 px-3 text-right">
                                                    <SmartDropdown
                                                        trigger={
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-7 w-7 p-0"
                                                            >
                                                                <MoreVertical className="h-4 w-4" />
                                                            </Button>
                                                        }
                                                        isOpen={openMenuId === `hlzf-${item.id}`}
                                                        onOpenChange={(isOpen) => setOpenMenuId(isOpen ? `hlzf-${item.id}` : null)}
                                                        className="bg-popover border rounded-md shadow-md py-1"
                                                    >
                                                        <button
                                                            className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2"
                                                            onClick={() => {
                                                                setOpenMenuId(null);
                                                                handleEditHLZF(item);
                                                            }}
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
                                                    </SmartDropdown>
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">No HLZF data available</p>
                )}
            </Card>

            {/* Source Files */}
            <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <FileDown className="h-5 w-5 text-orange-500" />
                        Source Files
                    </h2>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setUploadDialogOpen(true)}
                    >
                        <Upload className="mr-2 h-4 w-4" />
                        Upload Files
                    </Button>
                </div>
                {files.length > 0 ? (
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
                                <Button
                                    variant="outline"
                                    size="sm"
                                    asChild
                                >
                                    <a href={`${import.meta.env.VITE_API_URL}${file.path}`} download={file.name}>
                                        <FileDown className="mr-2 h-3 w-3" />
                                        Download
                                    </a>
                                </Button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-8">No source files available</p>
                )}
            </Card>

            {/* Upload Dialog */}
            <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Upload Files for {dno.name}</DialogTitle>
                        <DialogDescription>
                            Drop files here. The system will automatically detect the data type and year from the filename.
                        </DialogDescription>
                    </DialogHeader>

                    {/* File Input */}
                    <div
                        className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            type="file"
                            multiple
                            accept=".pdf,.xlsx,.html,.csv"
                            onChange={(e) => handleFileUpload(e.target.files)}
                            className="hidden"
                            ref={fileInputRef}
                        />
                        <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                        <p className="text-sm font-medium">Click to choose files</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Supports PDF, XLSX, HTML, CSV
                        </p>
                    </div>

                    {/* Upload Progress */}
                    {isUploading && (
                        <div className="flex items-center justify-center gap-2 py-4">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm">Uploading...</span>
                        </div>
                    )}

                    {/* Upload Results */}
                    {uploadResults.length > 0 && (
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {uploadResults.map((result, idx) => (
                                <div
                                    key={idx}
                                    className={cn(
                                        "flex items-start gap-2 p-2 rounded text-sm",
                                        result.success ? "bg-green-500/10" : "bg-red-500/10"
                                    )}
                                >
                                    {result.success ? (
                                        <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                                    ) : (
                                        <XCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
                                    )}
                                    <div className="min-w-0">
                                        <p className="font-medium truncate">{result.filename}</p>
                                        <p className="text-xs text-muted-foreground">{result.message}</p>
                                        {result.success && result.detected_type && (
                                            <p className="text-xs text-muted-foreground">
                                                Detected: {result.detected_type} {result.detected_year}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                setUploadDialogOpen(false);
                                setUploadResults([]);
                            }}
                        >
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

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
                                        <p className="font-medium flex items-center gap-2">
                                            {job.year} - {job.data_type}
                                            {job.job_type && job.job_type !== 'full' && (
                                                <Badge variant="outline" className="text-xs">
                                                    {job.job_type === 'crawl' ? 'Crawl Only' : 'Extract Only'}
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
                                    <label className="block text-sm font-medium mb-1.5 text-muted-foreground">Leistung (€/kW)</label>
                                    <div className="relative group">
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="w-full h-10 px-3 py-2 border rounded-md bg-background ring-offset-background transition-all focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                            value={editRecord.leistung ?? ''}
                                            onChange={(e) => setEditRecord({ ...editRecord, leistung: e.target.value ? parseFloat(e.target.value) : undefined })}
                                            placeholder="0.00"
                                        />
                                        <div className="absolute right-1 top-1 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button 
                                                type="button"
                                                className="p-0.5 hover:bg-muted rounded text-muted-foreground"
                                                onClick={() => setEditRecord({ ...editRecord, leistung: (editRecord.leistung || 0) + 1 })}
                                            >
                                                <ChevronUp className="h-3 w-3" />
                                            </button>
                                            <button 
                                                type="button"
                                                className="p-0.5 hover:bg-muted rounded text-muted-foreground"
                                                onClick={() => setEditRecord({ ...editRecord, leistung: Math.max(0, (editRecord.leistung || 0) - 1) })}
                                            >
                                                <ChevronDown className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1.5 text-muted-foreground">Arbeit (ct/kWh)</label>
                                    <div className="relative group">
                                        <input
                                            type="number"
                                            step="0.001"
                                            className="w-full h-10 px-3 py-2 border rounded-md bg-background ring-offset-background transition-all focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                            value={editRecord.arbeit ?? ''}
                                            onChange={(e) => setEditRecord({ ...editRecord, arbeit: e.target.value ? parseFloat(e.target.value) : undefined })}
                                            placeholder="0.000"
                                        />
                                        <div className="absolute right-1 top-1 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button 
                                                type="button"
                                                className="p-0.5 hover:bg-muted rounded text-muted-foreground"
                                                onClick={() => setEditRecord({ ...editRecord, arbeit: (editRecord.arbeit || 0) + 0.1 })}
                                            >
                                                <ChevronUp className="h-3 w-3" />
                                            </button>
                                            <button 
                                                type="button"
                                                className="p-0.5 hover:bg-muted rounded text-muted-foreground"
                                                onClick={() => setEditRecord({ ...editRecord, arbeit: Math.max(0, (editRecord.arbeit || 0) - 0.1) })}
                                            >
                                                <ChevronDown className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <p className="text-sm text-muted-foreground mb-2">Enter time ranges (comma-separated, e.g., "08:00 - 12:00, 17:00 - 19:00")</p>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Winter</label>
                                    <Input
                                        type="text"
                                        value={editRecord.winter ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, winter: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Frühling</label>
                                    <Input
                                        type="text"
                                        value={editRecord.fruehling ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, fruehling: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Sommer</label>
                                    <Input
                                        type="text"
                                        value={editRecord.sommer ?? ''}
                                        onChange={(e) => setEditRecord({ ...editRecord, sommer: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1">Herbst</label>
                                    <Input
                                        type="text"
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
