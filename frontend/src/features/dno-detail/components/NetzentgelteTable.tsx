/**
 * NetzentgelteTable - Data table for Netzentgelte records
 */

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Zap, Loader2, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { VerificationBadge } from "@/components/VerificationBadge";
import { ExtractionSourceBadge } from "@/components/ExtractionSourceBadge";
import { SmartDropdown } from "@/components/SmartDropdown";
import type { Netzentgelte } from "@/lib/api";

interface NetzentgelteTableProps {
    data: Netzentgelte[];
    isLoading: boolean;
    dnoId: number | string;
    isAdmin: boolean;
    onEdit: (item: Netzentgelte) => void;
    onDelete: (recordId: number) => void;
    openMenuId: string | null;
    onMenuOpenChange: (id: string | null) => void;
}

export function NetzentgelteTable({
    data,
    isLoading,
    dnoId,
    isAdmin,
    onEdit,
    onDelete,
    openMenuId,
    onMenuOpenChange,
}: NetzentgelteTableProps) {
    return (
        <Card className="p-6 min-h-[320px]">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Zap className="h-5 w-5 text-blue-500" />
                Netzentgelte
            </h2>

            {isLoading ? (
                <div className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : data.length > 0 ? (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b">
                                <th className="text-left py-2 px-3 font-medium text-muted-foreground" rowSpan={2}>
                                    Year
                                </th>
                                <th className="text-left py-2 px-3 font-medium text-muted-foreground" rowSpan={2}>
                                    Voltage Level
                                </th>
                                <th
                                    className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50"
                                    colSpan={2}
                                >
                                    {"≥ 2.500 h/a"}
                                </th>
                                <th
                                    className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50"
                                    colSpan={2}
                                >
                                    {"< 2.500 h/a"}
                                </th>
                                <th
                                    className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50"
                                    rowSpan={2}
                                >
                                    Status
                                </th>
                                {isAdmin && (
                                    <th className="text-right py-2 px-3 font-medium text-muted-foreground w-16" rowSpan={2} />
                                )}
                            </tr>
                            <tr className="border-b text-xs">
                                <th className="text-right py-1 px-3 font-normal text-muted-foreground border-l border-border/50">
                                    Leistung (€/kW)
                                </th>
                                <th className="text-right py-1 px-3 font-normal text-muted-foreground">
                                    Arbeit (ct/kWh)
                                </th>
                                <th className="text-right py-1 px-3 font-normal text-muted-foreground border-l border-border/50">
                                    Leistung (€/kW)
                                </th>
                                <th className="text-right py-1 px-3 font-normal text-muted-foreground">
                                    Arbeit (ct/kWh)
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((item) => (
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
                                        <span className="select-all">
                                            {item.leistung_unter_2500h?.toFixed(2) || item.leistung?.toFixed(2) || "-"}
                                        </span>
                                    </td>
                                    <td className="py-2 px-3 text-right font-mono">
                                        <span className="select-all">
                                            {item.arbeit_unter_2500h?.toFixed(3) || item.arbeit?.toFixed(3) || "-"}
                                        </span>
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
                                                dnoId={String(dnoId)}
                                                compact
                                            />
                                        </div>
                                    </td>
                                    {isAdmin && (
                                        <td className="py-2 px-3 text-right">
                                            <SmartDropdown
                                                trigger={
                                                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                }
                                                isOpen={openMenuId === `netz-${item.id}`}
                                                onOpenChange={(isOpen) =>
                                                    { onMenuOpenChange(isOpen ? `netz-${item.id}` : null); }
                                                }
                                                className="bg-popover border rounded-md shadow-md py-1"
                                            >
                                                <button
                                                    className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2"
                                                    onClick={() => {
                                                        onMenuOpenChange(null);
                                                        onEdit(item);
                                                    }}
                                                >
                                                    <Pencil className="h-3.5 w-3.5" /> Edit
                                                </button>
                                                <button
                                                    className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted flex items-center gap-2 text-destructive"
                                                    onClick={() => {
                                                        onMenuOpenChange(null);
                                                        onDelete(item.id);
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
    );
}
