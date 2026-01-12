/**
 * DNODetailPage - Refactored to use extracted components
 * 
 * This page displays detailed information about a DNO including:
 * - Header with navigation and actions
 * - Statistics cards
 * - Data tables (Netzentgelte, HLZF)
 * - Files and jobs panel
 * - Import/Export functionality
 */

import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Netzentgelte, type HLZF, type Job } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    ArrowLeft,
    Loader2,
    Zap,
    Clock,
    Upload,
    Download,
    FolderInput,
    Check,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/use-auth";
import { useState, useMemo, useRef, useEffect } from "react";

// Import extracted components
import {
    EditDNODialog,
    DeleteDNODialog,
    NetzentgelteTable,
    HLZFTable,
    EditRecordDialog,
    FilesJobsPanel,
    DNOHeader,
    SourceDataAccordion,
} from "@/features/dno-detail";

// Import extracted hooks
import { useDataFilters, useDataCompleteness } from "@/features/dno-detail";

export function DNODetailPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { toast } = useToast();
    const { isAdmin } = useAuth();

    // Dropdown menu state for tables
    const [openMenuId, setOpenMenuId] = useState<string | null>(null);

    // Edit record modal state
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

    // Dialog states
    const [editDNOOpen, setEditDNOOpen] = useState(false);
    const [deleteDNOOpen, setDeleteDNOOpen] = useState(false);
    const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

    // Upload state
    const [uploadResults, setUploadResults] = useState<{
        filename: string;
        success: boolean;
        message: string;
        detected_type?: string | null;
        detected_year?: number | null;
    }[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [exportDataTypes, setExportDataTypes] = useState<string[]>(["netzentgelte", "hlzf"]);
    const [exportYears] = useState<number[]>([]);
    const [isExporting, setIsExporting] = useState(false);
    const [importDialogOpen, setImportDialogOpen] = useState(false);
    const [importMode, setImportMode] = useState<"merge" | "replace">("merge");
    const [importData, setImportData] = useState<{
        netzentgelte: unknown[];
        hlzf: unknown[];
    } | null>(null);
    const [importFileName, setImportFileName] = useState<string>("");
    const [isImporting, setIsImporting] = useState(false);
    const [deleteConfirmed, setDeleteConfirmed] = useState(false);
    const importFileRef = useRef<HTMLInputElement>(null);


    const [_showMoreDetails] = useState(false);

    // ===== DATA FETCHING =====

    // Fetch DNO details
    const { data: dnoResponse, isLoading: dnoLoading, error: dnoError } = useQuery({
        queryKey: ["dno", id],
        queryFn: () => api.dnos.get(id!),
        enabled: !!id,
        staleTime: 0,
        refetchOnMount: 'always',
    });

    const dno = dnoResponse?.data;
    const numericId = dno?.id;

    // Redirect slug URLs to numeric ID URLs
    useEffect(() => {
        if (numericId && id && !id.match(/^\d+$/) && String(numericId) !== id) {
            navigate(`/dnos/${numericId}`, { replace: true });
        }
    }, [numericId, id, navigate]);

    // Fetch jobs (with polling)
    const { data: jobsResponse, isLoading: jobsLoading } = useQuery({
        queryKey: ["dno-jobs", numericId],
        queryFn: () => api.dnos.getJobs(String(numericId), 20),
        enabled: !!numericId,
        staleTime: 0,
        refetchOnMount: 'always',
        refetchInterval: (query) => {
            const jobs = query.state.data?.data || [];
            const hasActiveJobs = jobs.some((job: { status: string }) =>
                job.status === "pending" || job.status === "running"
            );
            return hasActiveJobs ? 3000 : false;
        },
    });

    const jobs: Job[] = (jobsResponse?.data || []);
    const hasActiveJobs = useMemo(() =>
        jobs.some((job: { status: string }) =>
            job.status === "pending" || job.status === "running"
        ),
        [jobs]
    );

    // Fetch DNO data (netzentgelte, hlzf)
    const { data: dataResponse, isLoading: dataLoading, refetch: refetchData } = useQuery({
        queryKey: ["dno-data", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: !!numericId,
        staleTime: 0,
        refetchOnMount: 'always',
        refetchInterval: hasActiveJobs ? 5000 : false,
    });

    const dnoData = dataResponse?.data;
    const netzentgelte = dnoData?.netzentgelte || [];
    const hlzf = dnoData?.hlzf || [];

    // Fetch files
    const { data: filesResponse } = useQuery({
        queryKey: ["dno-files", numericId],
        queryFn: () => api.dnos.getFiles(String(numericId)),
        enabled: !!numericId,
        staleTime: 0,
        refetchOnMount: 'always',
        refetchInterval: hasActiveJobs ? 5000 : false,
    });

    const files = filesResponse?.data || [];

    // ===== CUSTOM HOOKS =====

    // Use the extracted filter hook
    const {
        yearFilter,
        voltageLevelFilter,
        filterOptions,
        toggleYearFilter,
        toggleVoltageLevelFilter,
        filteredNetzentgelte,
        filteredHLZF,
    } = useDataFilters({ netzentgelte, hlzf });

    // Use the extracted completeness hook
    const dataCompleteness = useDataCompleteness({ netzentgelte, hlzf });

    // ===== MUTATIONS =====

    // Trigger crawl mutation
    const triggerCrawlMutation = useMutation({
        mutationFn: async ({ years, dataType, jobType }: {
            years: number[];
            dataType: 'all' | 'netzentgelte' | 'hlzf';
            jobType: 'full' | 'crawl' | 'extract';
        }) => {
            const typesToCrawl = dataType === 'all' ? ['netzentgelte', 'hlzf'] as const : [dataType];
            const results = [];
            for (const year of years) {
                for (const type of typesToCrawl) {
                    const result = await api.dnos.triggerCrawl(String(numericId), {
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
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to trigger crawl", description: message });
        },
    });

    // Delete mutations
    const deleteNetzentgelteMutation = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteNetzentgelte(String(numericId), recordId),
        onSuccess: () => {
            toast({ title: "Record deleted", description: "The Netzentgelte record has been deleted" });
            refetchData();
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to delete record", description: message });
        },
    });

    const deleteHLZFMutation = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteHLZF(String(numericId), recordId),
        onSuccess: () => {
            toast({ title: "Record deleted", description: "The HLZF record has been deleted" });
            refetchData();
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to delete record", description: message });
        },
    });

    // Update mutations
    const updateNetzentgelteMutation = useMutation({
        mutationFn: (data: { id: number; leistung?: number; arbeit?: number }) =>
            api.dnos.updateNetzentgelte(String(numericId), data.id, { leistung: data.leistung, arbeit: data.arbeit }),
        onSuccess: () => {
            toast({ title: "Record updated", description: "The Netzentgelte record has been updated" });
            setEditModalOpen(false);
            setEditRecord(null);
            refetchData();
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to update record", description: message });
        },
    });

    const updateHLZFMutation = useMutation({
        mutationFn: (data: { id: number; winter?: string; fruehling?: string; sommer?: string; herbst?: string }) =>
            api.dnos.updateHLZF(String(numericId), data.id, { winter: data.winter, fruehling: data.fruehling, sommer: data.sommer, herbst: data.herbst }),
        onSuccess: () => {
            toast({ title: "Record updated", description: "The HLZF record has been updated" });
            setEditModalOpen(false);
            setEditRecord(null);
            refetchData();
        },
        onError: (error: unknown) => {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Unknown error";
            toast({ variant: "destructive", title: "Failed to update record", description: message });
        },
    });

    // Update DNO mutation
    const updateDNOMutation = useMutation({
        mutationFn: (data: { name?: string; region?: string; website?: string; description?: string; phone?: string; email?: string; contact_address?: string }) =>
            api.dnos.updateDNO(String(numericId), data),
        onSuccess: () => {
            toast({ title: "DNO updated", description: "Metadata saved successfully" });
            setEditDNOOpen(false);
            queryClient.invalidateQueries({ queryKey: ["dno", id] });
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
        mutationFn: () => api.dnos.deleteDNO(String(numericId)),
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

    // ===== HANDLERS =====

    const handleEditNetzentgelte = (item: Netzentgelte) => {
        setEditModalType('netzentgelte');
        setEditRecord({ id: item.id, leistung: item.leistung ?? undefined, arbeit: item.arbeit ?? undefined });
        setEditModalOpen(true);
    };

    const handleEditHLZF = (item: HLZF) => {
        setEditModalType('hlzf');
        setEditRecord({
            id: item.id,
            winter: item.winter || '',
            fruehling: item.fruehling || '',
            sommer: item.sommer || '',
            herbst: item.herbst || ''
        });
        setEditModalOpen(true);
    };

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

    const handleFileUpload = async (files: FileList | null) => {
        if (!files || files.length === 0 || !numericId) return;
        setIsUploading(true);
        setUploadResults([]);

        const results: typeof uploadResults = [];
        for (const file of Array.from(files)) {
            try {
                const response = await api.dnos.uploadFile(String(numericId), file);
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
                        message: response.message || 'Detection failed',
                    });
                }
            } catch {
                results.push({ filename: file.name, success: false, message: 'Upload failed' });
            }
        }

        setUploadResults(results);
        setIsUploading(false);
        queryClient.invalidateQueries({ queryKey: ["dno-files", numericId] });

        const successCount = results.filter(r => r.success).length;
        if (successCount > 0) {
            toast({ title: "Files Uploaded", description: `${successCount} of ${results.length} file(s) uploaded successfully` });
        }
    };

    const handleExport = async () => {
        if (!numericId) return;
        setIsExporting(true);
        try {
            const blob = await api.dnos.exportData(String(numericId), {
                data_types: exportDataTypes,
                years: exportYears.length > 0 ? exportYears : undefined,
                include_metadata: true,
            });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${dno?.slug || "dno"}-export-${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            toast({ title: "Export Complete", description: "JSON file downloaded successfully" });
        } catch (error) {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Export failed";
            toast({ variant: "destructive", title: "Export Failed", description: message });
        } finally {
            setIsExporting(false);
        }
    };

    const handleImportFileSelect = async (files: FileList | null) => {
        if (!files || files.length === 0) return;
        const file = files[0];
        setImportFileName(file.name);

        try {
            const text = await file.text();
            const data = JSON.parse(text);
            setImportData({
                netzentgelte: data.netzentgelte || [],
                hlzf: data.hlzf || [],
            });
            setImportDialogOpen(true);
        } catch {
            toast({ variant: "destructive", title: "Invalid File", description: "Could not parse JSON file" });
        }
    };

    const handleImport = async () => {
        if (!numericId || !importData) return;
        setIsImporting(true);
        try {
            await api.dnos.importData(String(numericId), {
                // Cast to any since import data comes from JSON file and may not match exact types
                netzentgelte: importData.netzentgelte as [],
                hlzf: importData.hlzf as [],
                mode: importMode,
            });
            toast({ title: "Import Complete", description: "Data imported successfully" });
            setImportDialogOpen(false);
            setImportData(null);
            refetchData();
        } catch (error) {
            const message = error instanceof AxiosError
                ? error.response?.data?.detail ?? error.message
                : "Import failed";
            toast({ variant: "destructive", title: "Import Failed", description: message });
        } finally {
            setIsImporting(false);
        }
    };

    // ===== LOADING & ERROR STATES =====

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

    // ===== RENDER =====

    return (
        <div className="space-y-6">
            {/* Header with navigation and actions */}
            <DNOHeader
                dno={dno}
                isAdmin={isAdmin()}
                onEditClick={() => { setEditDNOOpen(true); }}
                onDeleteClick={() => { setDeleteDNOOpen(true); }}
                onTriggerCrawl={(params) => { triggerCrawlMutation.mutate(params); }}
                isCrawlPending={triggerCrawlMutation.isPending}
            />

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
                            <Zap className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">Netzentgelte Records</p>
                            <p className="text-2xl font-bold">{dataCompleteness.netzentgelte.valid}</p>
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
                            <p className="text-2xl font-bold">{dataCompleteness.hlzf.valid}</p>
                        </div>
                    </div>
                </Card>
                <Card
                    className="p-4 cursor-help"
                    title={`Data Completeness: ${dataCompleteness.percentage.toFixed(0)}%\n\nNetzentgelte: ${dataCompleteness.netzentgelte.percentage.toFixed(0)}%\nHLZF: ${dataCompleteness.hlzf.percentage.toFixed(0)}%`}
                >
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
                            <p className="text-xs text-muted-foreground">
                                {dataCompleteness.voltageLevels} levels × {dataCompleteness.years} yrs
                            </p>
                        </div>
                    </div>
                </Card>
            </div>

            {/* DNO Details Card */}
            <Card className="p-4">
                <h2 className="text-sm font-semibold text-muted-foreground mb-3">Details</h2>
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
                </dl>

                {/* Source Data Accordion */}
                <div className="mt-4 pt-4 border-t">
                    <SourceDataAccordion
                        hasMastr={!!dno.has_mastr}
                        hasVnb={!!dno.has_vnb}
                        hasBdew={!!dno.has_bdew}
                        mastrData={dno.mastr_data}
                        vnbData={dno.vnb_data}
                        bdewData={dno.bdew_data}
                    />
                </div>
            </Card>

            {/* Filter Controls */}
            <Card className="p-4">
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">Year:</span>
                        <div className="flex flex-wrap gap-1">
                            {filterOptions.years.map(year => (
                                <button
                                    key={year}
                                    onClick={() => { toggleYearFilter(year); }}
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
                    </div>
                    {filterOptions.voltageLevels.length > 0 && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Voltage:</span>
                            <div className="flex flex-wrap gap-1">
                                {filterOptions.voltageLevels.map(level => (
                                    <button
                                        key={level}
                                        onClick={() => { toggleVoltageLevelFilter(level); }}
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
                        </div>
                    )}
                </div>
            </Card>

            {/* Netzentgelte Table */}
            <NetzentgelteTable
                data={filteredNetzentgelte}
                isLoading={dataLoading}
                dnoId={String(numericId)}
                isAdmin={isAdmin()}
                onEdit={handleEditNetzentgelte}
                onDelete={(recordId) => { deleteNetzentgelteMutation.mutate(recordId); }}
                openMenuId={openMenuId}
                onMenuOpenChange={setOpenMenuId}
            />

            {/* HLZF Table */}
            <HLZFTable
                data={filteredHLZF}
                isLoading={dataLoading}
                dnoId={numericId!}
                isAdmin={isAdmin()}
                onEdit={handleEditHLZF}
                onDelete={(recordId) => { deleteHLZFMutation.mutate(recordId); }}
                openMenuId={openMenuId}
                onMenuOpenChange={setOpenMenuId}
            />

            {/* Import/Export Section */}
            <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <FolderInput className="h-5 w-5 text-purple-500" />
                    Import / Export Data
                </h2>
                <div className="grid md:grid-cols-2 gap-6">
                    {/* Export Side */}
                    <div className="space-y-4">
                        <h3 className="font-medium flex items-center gap-2">
                            <Download className="h-4 w-4" />
                            Export as JSON
                        </h3>
                        <div className="space-y-3">
                            <div>
                                <label className="text-sm font-medium mb-2 block">Data Types</label>
                                <div className="flex gap-2">
                                    {["netzentgelte", "hlzf"].map(type => (
                                        <button
                                            key={type}
                                            type="button"
                                            onClick={() => {
                                                if (exportDataTypes.includes(type)) {
                                                    setExportDataTypes(exportDataTypes.filter(t => t !== type));
                                                } else {
                                                    setExportDataTypes([...exportDataTypes, type]);
                                                }
                                            }}
                                            className={cn(
                                                "flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border transition-colors",
                                                exportDataTypes.includes(type)
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-background border-input hover:bg-muted"
                                            )}
                                        >
                                            {exportDataTypes.includes(type) && <Check className="h-3 w-3" />}
                                            {type === "netzentgelte" ? "Netzentgelte" : "HLZF"}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                disabled={
                                    dataLoading ||
                                    netzentgelte.length === 0 ||
                                    isExporting
                                }
                                onClick={() => handleExport()}
                            >
                                {isExporting ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Exporting...
                                    </>
                                ) : (
                                    <>
                                        <Download className="mr-2 h-4 w-4" />
                                        Export Selected Data
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>

                    {/* Import Side */}
                    <div className="space-y-4">
                        <h3 className="font-medium flex items-center gap-2">
                            <Upload className="h-4 w-4" />
                            Import from JSON
                        </h3>
                        <div
                            className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
                            onClick={() => importFileRef.current?.click()}
                        >
                            <input
                                type="file"
                                accept=".json"
                                onChange={(e) => handleImportFileSelect(e.target.files)}
                                className="hidden"
                                ref={importFileRef}
                            />
                            <Upload className="mx-auto h-6 w-6 text-muted-foreground mb-2" />
                            <p className="text-sm font-medium">Drop JSON file or click to browse</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                Accepts exported JSON files
                            </p>
                        </div>
                    </div>
                </div>
            </Card>

            {/* Files & Jobs Panel */}
            <FilesJobsPanel
                files={files}
                jobs={jobs}
                jobsLoading={jobsLoading}
                onUploadClick={() => { setUploadDialogOpen(true); }}
            />

            {/* ===== DIALOGS ===== */}

            {/* Edit DNO Dialog */}
            <EditDNODialog
                open={editDNOOpen}
                onOpenChange={setEditDNOOpen}
                dnoName={dno.name}
                initialData={{
                    name: dno.name || '',
                    region: dno.region || '',
                    website: dno.website || '',
                    description: dno.description || '',
                    phone: dno.phone || '',
                    email: dno.email || '',
                    contact_address: dno.contact_address || '',
                }}
                onSave={(data) => { updateDNOMutation.mutate(data); }}
                isPending={updateDNOMutation.isPending}
            />

            {/* Delete DNO Dialog */}
            <DeleteDNODialog
                open={deleteDNOOpen}
                onOpenChange={setDeleteDNOOpen}
                dnoName={dno.name}
                onConfirm={() => { deleteDNOMutation.mutate(); }}
                isPending={deleteDNOMutation.isPending}
            />

            {/* Edit Record Dialog */}
            <EditRecordDialog
                open={editModalOpen}
                onOpenChange={setEditModalOpen}
                recordType={editModalType}
                editData={editRecord}
                onDataChange={setEditRecord}
                onSave={handleSaveEdit}
                isPending={updateNetzentgelteMutation.isPending || updateHLZFMutation.isPending}
            />

            {/* Upload Dialog */}
            <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Upload Source Files</DialogTitle>
                        <DialogDescription>
                            Upload PDF or Excel files containing Netzentgelte or HLZF data.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div
                            className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <input
                                type="file"
                                accept=".pdf,.xlsx,.xls"
                                multiple
                                onChange={(e) => handleFileUpload(e.target.files)}
                                className="hidden"
                                ref={fileInputRef}
                            />
                            <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-3" />
                            <p className="font-medium">Drop files or click to browse</p>
                            <p className="text-sm text-muted-foreground mt-1">
                                Supports PDF and Excel files
                            </p>
                        </div>
                        {isUploading && (
                            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Uploading...
                            </div>
                        )}
                        {uploadResults.length > 0 && (
                            <div className="space-y-2">
                                {uploadResults.map((result, i) => (
                                    <div
                                        key={i}
                                        className={cn(
                                            "p-3 rounded-lg text-sm",
                                            result.success
                                                ? "bg-green-500/10 text-green-700 dark:text-green-300"
                                                : "bg-red-500/10 text-red-700 dark:text-red-300"
                                        )}
                                    >
                                        <p className="font-medium">{result.filename}</p>
                                        <p className="text-xs opacity-80">{result.message}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setUploadDialogOpen(false); }}>
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Import Preview Dialog */}
            <Dialog open={importDialogOpen} onOpenChange={(open) => {
                setImportDialogOpen(open);
                if (!open) setDeleteConfirmed(false); // Reset confirmation when dialog closes
            }}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Import Data</DialogTitle>
                        <DialogDescription>
                            Importing from: {importFileName}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div className="p-3 bg-muted rounded-lg">
                                <p className="font-medium">Netzentgelte</p>
                                <p className="text-2xl font-bold">{importData?.netzentgelte.length || 0}</p>
                                <p className="text-xs text-muted-foreground">records</p>
                            </div>
                            <div className="p-3 bg-muted rounded-lg">
                                <p className="font-medium">HLZF</p>
                                <p className="text-2xl font-bold">{importData?.hlzf.length || 0}</p>
                                <p className="text-xs text-muted-foreground">records</p>
                            </div>
                        </div>
                        <div>
                            <label className="text-sm font-medium mb-2 block">Import Mode</label>
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => { setImportMode("merge"); setDeleteConfirmed(false); }}
                                    className={cn(
                                        "flex-1 px-3 py-2 text-sm rounded-md border transition-colors",
                                        importMode === "merge"
                                            ? "bg-primary text-primary-foreground border-primary"
                                            : "bg-background border-input hover:bg-muted"
                                    )}
                                >
                                    Merge (Add/Update)
                                </button>
                                <button
                                    type="button"
                                    onClick={() => { setImportMode("replace"); }}
                                    className={cn(
                                        "flex-1 px-3 py-2 text-sm rounded-md border transition-colors",
                                        importMode === "replace"
                                            ? "bg-destructive text-destructive-foreground border-destructive"
                                            : "bg-background border-input hover:bg-muted"
                                    )}
                                >
                                    Replace All
                                </button>
                            </div>
                        </div>

                        {/* Warning for replace mode with empty arrays */}
                        {importMode === "replace" && importData &&
                            (importData.netzentgelte.length === 0 || importData.hlzf.length === 0) && (
                                <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/30 space-y-3">
                                    <div className="flex items-start gap-2">
                                        <svg className="h-5 w-5 text-destructive shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                        </svg>
                                        <div className="text-sm">
                                            <p className="font-semibold text-destructive">Warning: This will delete ALL data!</p>
                                            <p className="text-muted-foreground mt-1">
                                                {importData.netzentgelte.length === 0 && importData.hlzf.length === 0
                                                    ? "Both Netzentgelte and HLZF arrays are empty. All records for this DNO will be permanently deleted."
                                                    : importData.netzentgelte.length === 0
                                                        ? "Netzentgelte array is empty. All Netzentgelte records for this DNO will be permanently deleted."
                                                        : "HLZF array is empty. All HLZF records for this DNO will be permanently deleted."
                                                }
                                            </p>
                                        </div>
                                    </div>
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={deleteConfirmed}
                                            onChange={(e) => setDeleteConfirmed(e.target.checked)}
                                            className="h-4 w-4 rounded border-destructive text-destructive focus:ring-destructive"
                                        />
                                        <span className="text-sm font-medium">I understand and want to delete all data</span>
                                    </label>
                                </div>
                            )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setImportDialogOpen(false); }}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleImport}
                            disabled={
                                isImporting ||
                                ((importMode === "replace" &&
                                    importData &&
                                    (importData.netzentgelte.length === 0 || importData.hlzf.length === 0) &&
                                    !deleteConfirmed) || false)
                            }
                            variant={importMode === "replace" && importData &&
                                (importData.netzentgelte.length === 0 || importData.hlzf.length === 0)
                                ? "destructive" : "default"}
                        >
                            {isImporting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Importing...
                                </>
                            ) : (
                                importMode === "replace" && importData &&
                                    (importData.netzentgelte.length === 0 || importData.hlzf.length === 0)
                                    ? "Delete & Import"
                                    : "Import Data"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
