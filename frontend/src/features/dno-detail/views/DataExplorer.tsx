import { useState, useRef } from "react";
import { useOutletContext } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, type Netzentgelte, type HLZF } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Upload, Download, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
    NetzentgelteTable,
    HLZFTable,
    EditRecordDialog,
} from "../components";
import { useDataFilters } from "../hooks";
import type { DNODetailContext } from "./types";

export function DataExplorer() {
    const { numericId, isAdmin } = useOutletContext<DNODetailContext>();
    const { toast } = useToast();

    // Local state
    const [openMenuId, setOpenMenuId] = useState<string | null>(null);
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
    const [isExporting, setIsExporting] = useState(false);
    const importFileRef = useRef<HTMLInputElement>(null);

    // Fetch data
    const { data: dataResponse, isLoading: dataLoading, refetch: refetchData } = useQuery({
        queryKey: ["dno-data", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: !!numericId,
    });

    const netzentgelte = dataResponse?.data?.netzentgelte || [];
    const hlzf = dataResponse?.data?.hlzf || [];

    // Filters
    const {
        yearFilter,
        voltageLevelFilter,
        filterOptions,
        toggleYearFilter,
        toggleVoltageLevelFilter,
        filteredNetzentgelte,
        filteredHLZF,
    } = useDataFilters({ netzentgelte, hlzf });

    // Mutations
    const updateNetzentgelteMutation = useMutation({
        mutationFn: (data: { id: number; leistung?: number; arbeit?: number }) =>
            api.dnos.updateNetzentgelte(String(numericId), data.id, data),
        onSuccess: () => {
            setEditModalOpen(false);
            refetchData();
            toast({ title: "Updated", description: "Record updated." });
        },
        onError: () => { toast({ variant: "destructive", title: "Update Failed", description: "Could not update record." }); },
    });

    const updateHLZFMutation = useMutation({
        mutationFn: (data: { id: number; winter?: string; fruehling?: string; sommer?: string; herbst?: string }) =>
            api.dnos.updateHLZF(String(numericId), data.id, data),
        onSuccess: () => {
            setEditModalOpen(false);
            refetchData();
            toast({ title: "Updated", description: "Record updated." });
        },
        onError: () => { toast({ variant: "destructive", title: "Update Failed", description: "Could not update record." }); },
    });

    const deleteNetzentgelteMutation = useMutation({
        mutationFn: (rid: number) => api.dnos.deleteNetzentgelte(String(numericId), rid),
        onSuccess: () => { refetchData(); toast({ title: "Deleted", description: "Record removed." }); },
        onError: () => { toast({ variant: "destructive", title: "Delete Failed", description: "Could not delete record." }); },
    });

    const deleteHLZFMutation = useMutation({
        mutationFn: (rid: number) => api.dnos.deleteHLZF(String(numericId), rid),
        onSuccess: () => { refetchData(); toast({ title: "Deleted", description: "Record removed." }); },
        onError: () => { toast({ variant: "destructive", title: "Delete Failed", description: "Could not delete record." }); },
    });

    // Export handler
    const handleExport = async () => {
        if (!numericId) return;
        setIsExporting(true);
        try {
            const blob = await api.dnos.exportData(String(numericId), {
                data_types: ["netzentgelte", "hlzf"],
                years: [],
                include_metadata: true,
            });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `dno-${numericId}-export.json`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            toast({ title: "Exported", description: "Download started." });
        } catch {
            toast({ variant: "destructive", title: "Export Failed" });
        } finally { setIsExporting(false); }
    };

    // Import handler
    const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !numericId) return;
        try {
            const text = await file.text();
            const data = JSON.parse(text);
            await api.dnos.importData(String(numericId), {
                netzentgelte: data.netzentgelte || [],
                hlzf: data.hlzf || [],
                mode: "merge"
            });
            toast({ title: "Imported", description: "Data imported successfully." });
            refetchData();
        } catch {
            toast({ variant: "destructive", title: "Import Failed" });
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* Header with Import/Export */}
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Data Explorer</h2>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => importFileRef.current?.click()}>
                        <Upload className="mr-2 h-4 w-4" /> Import
                    </Button>
                    <input type="file" accept=".json" ref={importFileRef} className="hidden" onChange={handleImportFile} />

                    <Button variant="outline" size="sm" onClick={handleExport} disabled={isExporting}>
                        {isExporting ? <Loader2 className="animate-spin h-4 w-4" /> : <Download className="mr-2 h-4 w-4" />}
                        Export
                    </Button>
                </div>
            </div>

            {/* Filters Row */}
            <div className="flex flex-wrap gap-2 items-center bg-card/50 backdrop-blur-sm p-3 rounded-xl border border-[#34d399]/10 shadow-xl">
                <span className="text-xs font-semibold text-muted-foreground px-2">FILTERS</span>
                <div className="h-4 w-[1px] bg-border mx-1"></div>
                <span className="text-xs text-muted-foreground">Year:</span>
                {filterOptions.years.map(y => (
                    <Badge
                        key={y}
                        variant={yearFilter.includes(y) ? "default" : "outline"}
                        className="cursor-pointer hover:bg-primary/20"
                        onClick={() => toggleYearFilter(y)}
                    >
                        {y}
                    </Badge>
                ))}
                <div className="h-4 w-[1px] bg-border mx-1"></div>
                <span className="text-xs text-muted-foreground">Voltage:</span>
                {filterOptions.voltageLevels.map(v => (
                    <Badge
                        key={v}
                        variant={voltageLevelFilter.includes(v) ? "default" : "outline"}
                        className="cursor-pointer hover:bg-primary/20"
                        onClick={() => toggleVoltageLevelFilter(v)}
                    >
                        {v}
                    </Badge>
                ))}
            </div>

            {/* Netzentgelte Table */}
            <NetzentgelteTable
                data={filteredNetzentgelte}
                isLoading={dataLoading}
                dnoId={String(numericId)}
                isAdmin={isAdmin}
                onEdit={(item: Netzentgelte) => {
                    setEditModalType('netzentgelte');
                    setEditRecord({ id: item.id, leistung: item.leistung ?? undefined, arbeit: item.arbeit ?? undefined });
                    setEditModalOpen(true);
                }}
                onDelete={(id: number) => deleteNetzentgelteMutation.mutate(id)}
                openMenuId={openMenuId}
                onMenuOpenChange={setOpenMenuId}
            />

            {/* HLZF Table */}
            <HLZFTable
                data={filteredHLZF}
                isLoading={dataLoading}
                dnoId={numericId!}
                isAdmin={isAdmin}
                onEdit={(item: HLZF) => {
                    setEditModalType('hlzf');
                    setEditRecord({ id: item.id, winter: item.winter ?? '', fruehling: item.fruehling ?? '', sommer: item.sommer ?? '', herbst: item.herbst ?? '' });
                    setEditModalOpen(true);
                }}
                onDelete={(id: number) => deleteHLZFMutation.mutate(id)}
                openMenuId={openMenuId}
                onMenuOpenChange={setOpenMenuId}
            />

            <EditRecordDialog
                open={editModalOpen}
                onOpenChange={setEditModalOpen}
                recordType={editModalType}
                editData={editRecord}
                onDataChange={setEditRecord}
                onSave={() => {
                    if (!editRecord) return;
                    if (editModalType === 'netzentgelte') {
                        updateNetzentgelteMutation.mutate(editRecord);
                    } else {
                        updateHLZFMutation.mutate(editRecord);
                    }
                }}
                isPending={updateNetzentgelteMutation.isPending || updateHLZFMutation.isPending}
            />
        </div>
    );
}
