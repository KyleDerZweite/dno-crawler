/**
 * Custom hook for all DNO-related mutations
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useErrorToast } from "@/hooks/use-error-toast";

interface UseDNOMutationsOptions {
    dnoId: number | undefined;
    onSuccess?: () => void;
}

/**
 * Hook that provides all mutation functions for DNO operations
 */
export function useDNOMutations({ dnoId, onSuccess }: UseDNOMutationsOptions) {
    const { toast } = useToast();
    const { createErrorHandler } = useErrorToast();
    const queryClient = useQueryClient();

    const invalidateQueries = () => {
        if (dnoId) {
            queryClient.invalidateQueries({ queryKey: ["dno", dnoId] });
            queryClient.invalidateQueries({ queryKey: ["dno-data", dnoId] });
            queryClient.invalidateQueries({ queryKey: ["dno-jobs", dnoId] });
            queryClient.invalidateQueries({ queryKey: ["dno-files", dnoId] });
        }
    };

    // Trigger crawl mutation
    const triggerCrawl = useMutation({
        mutationFn: async ({
            years,
            dataType,
            jobType,
        }: {
            years: number[];
            dataType: "all" | "netzentgelte" | "hlzf";
            jobType: "full" | "crawl" | "extract";
        }) => {
            const typesToCrawl =
                dataType === "all" ? (["netzentgelte", "hlzf"] as const) : [dataType];
            const results = [];

            for (const year of years) {
                for (const type of typesToCrawl) {
                    const result = await api.dnos.triggerCrawl(String(dnoId), {
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
            const jobTypeLabel =
                variables.jobType === "full"
                    ? "Full"
                    : variables.jobType === "crawl"
                        ? "Crawl"
                        : "Extract";
            toast({
                title: `${jobTypeLabel} job${jobCount > 1 ? "s" : ""} triggered`,
                description: `${jobCount} job${jobCount > 1 ? "s" : ""} queued for years: ${variables.years.join(", ")}`,
            });
            invalidateQueries();
            onSuccess?.();
        },
        onError: createErrorHandler("Failed to trigger crawl"),
    });

    // Delete Netzentgelte
    const deleteNetzentgelte = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteNetzentgelte(String(dnoId), recordId),
        onSuccess: () => {
            toast({ title: "Record deleted", description: "The Netzentgelte record has been deleted" });
            invalidateQueries();
        },
        onError: createErrorHandler("Failed to delete record"),
    });

    // Delete HLZF
    const deleteHLZF = useMutation({
        mutationFn: (recordId: number) => api.dnos.deleteHLZF(String(dnoId), recordId),
        onSuccess: () => {
            toast({ title: "Record deleted", description: "The HLZF record has been deleted" });
            invalidateQueries();
        },
        onError: createErrorHandler("Failed to delete record"),
    });

    // Update Netzentgelte
    const updateNetzentgelte = useMutation({
        mutationFn: (data: { id: number; leistung?: number; arbeit?: number }) =>
            api.dnos.updateNetzentgelte(String(dnoId), data.id, {
                leistung: data.leistung,
                arbeit: data.arbeit,
            }),
        onSuccess: () => {
            toast({ title: "Record updated", description: "The Netzentgelte record has been updated" });
            invalidateQueries();
            onSuccess?.();
        },
        onError: createErrorHandler("Failed to update record"),
    });

    // Update HLZF
    const updateHLZF = useMutation({
        mutationFn: (data: {
            id: number;
            winter?: string;
            fruehling?: string;
            sommer?: string;
            herbst?: string;
        }) =>
            api.dnos.updateHLZF(String(dnoId), data.id, {
                winter: data.winter,
                fruehling: data.fruehling,
                sommer: data.sommer,
                herbst: data.herbst,
            }),
        onSuccess: () => {
            toast({ title: "Record updated", description: "The HLZF record has been updated" });
            invalidateQueries();
            onSuccess?.();
        },
        onError: createErrorHandler("Failed to update record"),
    });

    // Update DNO metadata
    const updateDNO = useMutation({
        mutationFn: (data: {
            name?: string;
            region?: string;
            website?: string;
            description?: string;
            phone?: string;
            email?: string;
            contact_address?: string;
        }) => api.dnos.updateDNO(String(dnoId), data),
        onSuccess: () => {
            toast({ title: "DNO updated", description: "Metadata saved successfully" });
            invalidateQueries();
            onSuccess?.();
        },
        onError: createErrorHandler("Failed to update DNO"),
    });

    // Delete DNO
    const deleteDNO = useMutation({
        mutationFn: () => api.dnos.deleteDNO(String(dnoId)),
        onSuccess: () => {
            toast({
                title: "DNO deleted",
                description: "DNO and all associated data have been permanently deleted",
            });
            queryClient.invalidateQueries({ queryKey: ["dnos"] });
        },
        onError: createErrorHandler("Failed to delete DNO"),
    });

    // Upload file
    const uploadFile = useMutation({
        mutationFn: (file: File) => api.dnos.uploadFile(String(dnoId), file),
        onSuccess: (response) => {
            if (response.success) {
                toast({ title: "File uploaded", description: `Saved as ${response.data.filename}` });
            }
            invalidateQueries();
        },
        onError: createErrorHandler("Failed to upload file"),
    });

    return {
        triggerCrawl,
        deleteNetzentgelte,
        deleteHLZF,
        updateNetzentgelte,
        updateHLZF,
        updateDNO,
        deleteDNO,
        uploadFile,
        // Convenience for checking if any mutation is pending
        isAnyPending:
            triggerCrawl.isPending ||
            deleteNetzentgelte.isPending ||
            deleteHLZF.isPending ||
            updateNetzentgelte.isPending ||
            updateHLZF.isPending ||
            updateDNO.isPending ||
            deleteDNO.isPending ||
            uploadFile.isPending,
    };
}
