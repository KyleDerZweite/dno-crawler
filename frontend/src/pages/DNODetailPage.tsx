/**
 * DNODetailPage - Lightweight Parent with Dual-Sidebar Layout
 * 
 * This page is a lightweight shell that:
 * - Fetches ONLY DNO metadata (no heavy data)
 * - Provides context to child views via Outlet
 * - Renders the Context Sidebar and content area
 * 
 * Heavy data fetching is delegated to child views for lazy loading.
 */

import { useParams, useNavigate, Outlet, Link, useLocation } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Home, ChevronRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/lib/use-auth";
import { useState, useEffect } from "react";
import {
    DetailContextSidebar,
    EditDNODialog,
    DeleteDNODialog,
} from "@/features/dno-detail";
import { useDataCompleteness } from "@/features/dno-detail";
import type { DNODetailContext } from "@/features/dno-detail/views";

// Nav item labels for breadcrumbs
const navLabels: Record<string, string> = {
    overview: "Overview",
    data: "Data Explorer",
    analysis: "Analysis",
    files: "Source Files",
    jobs: "Job History",
    tools: "Tools",
    technical: "Technical",
    sql: "SQL Explorer",
};

export function DNODetailPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const queryClient = useQueryClient();
    const { toast } = useToast();
    const { isAdmin } = useAuth();

    // Dialogs
    const [editDNOOpen, setEditDNOOpen] = useState(false);
    const [deleteDNOOpen, setDeleteDNOOpen] = useState(false);

    // Fetch DNO metadata only (lightweight)
    const { data: dnoResponse, isLoading: dnoLoading, error: dnoError } = useQuery({
        queryKey: ["dno", id],
        queryFn: () => api.dnos.get(id!),
        enabled: !!id,
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

    // Lightweight queries for sidebar counts and completeness
    const { data: jobsResponse } = useQuery({
        queryKey: ["dno-jobs-count", numericId],
        queryFn: () => api.dnos.getJobs(String(numericId), 1), // Just get count
        enabled: !!numericId,
    });

    const { data: filesResponse } = useQuery({
        queryKey: ["dno-files-count", numericId],
        queryFn: () => api.dnos.getFiles(String(numericId)),
        enabled: !!numericId,
    });

    const { data: dataResponse } = useQuery({
        queryKey: ["dno-data-summary", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: !!numericId,
    });

    const netzentgelte = dataResponse?.data?.netzentgelte || [];
    const hlzf = dataResponse?.data?.hlzf || [];
    const dataCompleteness = useDataCompleteness({ netzentgelte, hlzf });

    // Mutations
    const triggerCrawlMutation = useMutation({
        mutationFn: async ({ years, dataType, jobType }: { years: number[]; dataType: "all" | "netzentgelte" | "hlzf"; jobType: "full" | "crawl" | "extract" }) => {
            const types: ("netzentgelte" | "hlzf")[] = dataType === 'all' ? ['netzentgelte', 'hlzf'] : [dataType as "netzentgelte" | "hlzf"];
            const results = [];
            for (const year of years) {
                for (const type of types) {
                    results.push(await api.dnos.triggerCrawl(String(numericId), { year, data_type: type, job_type: jobType }));
                }
            }
            return results;
        },
        onSuccess: (results) => {
            toast({ title: "Jobs Triggered", description: `${results.length} jobs queued.` });
            queryClient.invalidateQueries({ queryKey: ["dno-jobs", numericId] });
        },
        onError: (err: Error) => toast({ variant: "destructive", title: "Error", description: err.message })
    });

    const updateDNOMutation = useMutation({
        mutationFn: (data: Parameters<typeof api.dnos.updateDNO>[1]) => api.dnos.updateDNO(String(numericId), data),
        onSuccess: () => {
            toast({ title: "Updated", description: "DNO metadata saved." });
            setEditDNOOpen(false);
            queryClient.invalidateQueries({ queryKey: ["dno", id] });
        },
        onError: () => { toast({ variant: "destructive", title: "Update Failed", description: "Could not update DNO." }); },
    });

    const deleteDNOMutation = useMutation({
        mutationFn: () => api.dnos.deleteDNO(String(numericId)),
        onSuccess: () => {
            navigate("/dnos");
            toast({ title: "Deleted", description: "DNO removed." });
        },
        onError: () => { toast({ variant: "destructive", title: "Delete Failed", description: "Could not delete DNO." }); },
    });

    // Loading/Error states
    if (dnoLoading) {
        return (
            <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
                <Loader2 className="animate-spin h-8 w-8 text-muted-foreground" />
            </div>
        );
    }

    if (dnoError || !dno) {
        return (
            <div className="p-8 text-center text-destructive">
                Error loading DNO
            </div>
        );
    }

    // Get current view from path
    const pathParts = location.pathname.split('/');
    const currentView = pathParts[pathParts.length - 1] || 'overview';

    // Context to pass to child views
    const outletContext: DNODetailContext = {
        dno,
        numericId: String(numericId),
        isAdmin: isAdmin(),
    };

    return (
        <div className="flex h-screen overflow-hidden bg-background">
            {/* Context Sidebar */}
            <DetailContextSidebar
                dno={dno}
                basePath={`/dnos/${numericId}`}
                isAdmin={isAdmin()}
                filesCount={filesResponse?.data?.length || 0}
                jobsCount={jobsResponse?.data?.length || 0}
                completeness={dataCompleteness}
                onEditClick={() => setEditDNOOpen(true)}
                onTriggerCrawl={(params) => triggerCrawlMutation.mutate(params)}
                isCrawlPending={triggerCrawlMutation.isPending}
            />

            {/* Workspace */}
            <main className="flex-1 flex flex-col min-w-0">
                {/* Breadcrumbs Header - h-16 to align with global sidebar header */}
                <header className="h-16 border-b px-6 flex items-center gap-2 bg-background/50 backdrop-blur shrink-0 sticky top-0 z-10">
                    <Button variant="ghost" size="icon" asChild className="h-8 w-8 -ml-2 text-muted-foreground">
                        <Link to="/dashboard"><Home className="h-4 w-4" /></Link>
                    </Button>
                    <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                    <Link to="/dnos" className="text-sm text-muted-foreground hover:text-foreground">DNOs</Link>
                    {dno.region && (
                        <>
                            <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                            <span className="text-sm text-muted-foreground">{dno.region}</span>
                        </>
                    )}
                    <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                    <span className="text-sm font-medium">{dno.name}</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                    <Badge variant="secondary" className="text-xs rounded-sm px-2 font-normal">
                        {navLabels[currentView] || "Overview"}
                    </Badge>
                </header>

                {/* Content Area - Child routes render here */}
                <div className="flex-1 overflow-y-auto p-6">
                    <div className="max-w-7xl mx-auto">
                        <Outlet context={outletContext} />
                    </div>
                </div>
            </main>

            {/* Dialogs */}
            <EditDNODialog
                open={editDNOOpen}
                onOpenChange={setEditDNOOpen}
                dnoName={dno.name}
                initialData={{
                    name: dno.name,
                    region: dno.region || "",
                    website: dno.website || "",
                    description: dno.description || "",
                    phone: dno.phone || "",
                    email: dno.email || "",
                    contact_address: dno.contact_address || "",
                }}
                onSave={updateDNOMutation.mutate}
                isPending={updateDNOMutation.isPending}
            />
            <DeleteDNODialog
                open={deleteDNOOpen}
                onOpenChange={setDeleteDNOOpen}
                dnoName={dno.name}
                onConfirm={deleteDNOMutation.mutate}
                isPending={deleteDNOMutation.isPending}
            />
        </div>
    );
}
