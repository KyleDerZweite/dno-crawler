/**
 * Custom hook for fetching DNO data with automatic polling
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useMemo } from "react";

interface UseDNODataOptions {
    dnoId: string | number | undefined;
    enabled?: boolean;
}

/**
 * Hook that manages all DNO-related data fetching with smart polling
 */
export function useDNOData({ dnoId, enabled = true }: UseDNODataOptions) {
    const numericId = typeof dnoId === "string" ? parseInt(dnoId, 10) : dnoId;
    const isEnabled = enabled && !!numericId && !isNaN(numericId);

    // Fetch DNO details
    const dnoQuery = useQuery({
        queryKey: ["dno", numericId],
        queryFn: () => api.dnos.get(String(numericId)),
        enabled: isEnabled,
        staleTime: 0,
        refetchOnMount: "always",
    });

    // Fetch jobs with polling when active
    const jobsQuery = useQuery({
        queryKey: ["dno-jobs", numericId],
        queryFn: () => api.dnos.getJobs(String(numericId), 20),
        enabled: isEnabled,
        staleTime: 0,
        refetchOnMount: "always",
        refetchInterval: (query) => {
            const jobs = query.state.data?.data || [];
            const hasActiveJobs = jobs.some(
                (job: { status: string }) =>
                    job.status === "pending" || job.status === "running"
            );
            return hasActiveJobs ? 3000 : false;
        },
    });

    // Check if there are active jobs
    const hasActiveJobs = useMemo(() => {
        const jobs = jobsQuery.data?.data || [];
        return jobs.some(
            (job: { status: string }) =>
                job.status === "pending" || job.status === "running"
        );
    }, [jobsQuery.data?.data]);

    // Fetch DNO data (netzentgelte, hlzf) with polling when jobs are active
    const dataQuery = useQuery({
        queryKey: ["dno-data", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: isEnabled,
        staleTime: 0,
        refetchOnMount: "always",
        refetchInterval: hasActiveJobs ? 5000 : false,
    });

    // Fetch available files with polling when jobs are active
    const filesQuery = useQuery({
        queryKey: ["dno-files", numericId],
        queryFn: () => api.dnos.getFiles(String(numericId)),
        enabled: isEnabled,
        staleTime: 0,
        refetchOnMount: "always",
        refetchInterval: hasActiveJobs ? 5000 : false,
    });

    return {
        // DNO
        dno: dnoQuery.data?.data,
        dnoLoading: dnoQuery.isLoading,
        dnoError: dnoQuery.error,
        refetchDNO: dnoQuery.refetch,

        // Jobs
        jobs: jobsQuery.data?.data || [],
        jobsLoading: jobsQuery.isLoading,
        hasActiveJobs,

        // Data
        netzentgelte: dataQuery.data?.data?.netzentgelte || [],
        hlzf: dataQuery.data?.data?.hlzf || [],
        dataLoading: dataQuery.isLoading,
        refetchData: dataQuery.refetch,

        // Files
        files: filesQuery.data?.data || [],
        filesLoading: filesQuery.isLoading,
        refetchFiles: filesQuery.refetch,

        // Computed
        numericId,
        isLoading: dnoQuery.isLoading || dataQuery.isLoading,
    };
}
