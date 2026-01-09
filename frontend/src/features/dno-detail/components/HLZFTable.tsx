/**
 * HLZFTable - Data table for HLZF (Hochlastzeitfenster) records
 */

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Clock, Loader2, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { VerificationBadge } from "@/components/VerificationBadge";
import { ExtractionSourceBadge } from "@/components/ExtractionSourceBadge";
import { SmartDropdown } from "@/components/SmartDropdown";
import type { HLZF } from "@/lib/api";

interface HLZFTableProps {
    data: HLZF[];
    isLoading: boolean;
    dnoId: number | string;
    isAdmin: boolean;
    onEdit: (item: HLZF) => void;
    onDelete: (recordId: number) => void;
    openMenuId: string | null;
    onMenuOpenChange: (id: string | null) => void;
}

/**
 * Selectable time component - allows click-to-select for easy copying
 */
function SelectableTime({ value }: { value: string }) {
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
            onMouseDown={(e) => { e.stopPropagation(); }}
            style={{ userSelect: "text" }}
        >
            {value}
        </span>
    );
}

/**
 * Render time ranges from parsed backend array
 */
function renderTimeRanges(
    ranges: { start: string; end: string }[] | null | undefined,
    rawValue: string | null | undefined
): React.ReactNode {
    // Use parsed ranges if available
    if (ranges && ranges.length > 0) {
        return (
            <div className="space-y-0.5" style={{ userSelect: "none" }}>
                {ranges.map((range, idx) => (
                    <div key={idx} className="text-sm whitespace-nowrap flex items-center">
                        <SelectableTime value={range.start} />
                        <span className="text-muted-foreground px-1" style={{ userSelect: "none" }}>
                            –
                        </span>
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
}

export function HLZFTable({
    data,
    isLoading,
    dnoId,
    isAdmin,
    onEdit,
    onDelete,
    openMenuId,
    onMenuOpenChange,
}: HLZFTableProps) {
    return (
        <Card className="p-6 min-h-[320px]">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Clock className="h-5 w-5 text-purple-500" />
                HLZF (Hochlastzeitfenster)
            </h2>

            {isLoading ? (
                <div className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : data.length > 0 ? (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm table-fixed">
                        <thead>
                            <tr className="border-b">
                                <th className="text-left py-2 px-3 font-medium text-muted-foreground w-16">
                                    Year
                                </th>
                                <th className="text-left py-2 px-3 font-medium text-muted-foreground w-20">
                                    Voltage Level
                                </th>
                                <th
                                    className="text-left py-2 px-3 font-medium text-muted-foreground"
                                    style={{ width: "16%" }}
                                >
                                    Winter
                                </th>
                                <th
                                    className="text-left py-2 px-3 font-medium text-muted-foreground"
                                    style={{ width: "16%" }}
                                >
                                    Frühling
                                </th>
                                <th
                                    className="text-left py-2 px-3 font-medium text-muted-foreground"
                                    style={{ width: "16%" }}
                                >
                                    Sommer
                                </th>
                                <th
                                    className="text-left py-2 px-3 font-medium text-muted-foreground"
                                    style={{ width: "16%" }}
                                >
                                    Herbst
                                </th>
                                <th className="text-center py-2 px-3 font-medium text-muted-foreground w-24">
                                    Status
                                </th>
                                {isAdmin && (
                                    <th className="text-right py-2 px-3 font-medium text-muted-foreground w-12" />
                                )}
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((item) => (
                                <tr key={item.id} className="border-b border-border/50 hover:bg-muted/50">
                                    <td className="py-2 px-3">{item.year}</td>
                                    <td className="py-2 px-3 font-medium">{item.voltage_level}</td>
                                    <td className="py-2 px-3 font-mono align-top">
                                        {renderTimeRanges(item.winter_ranges, item.winter)}
                                    </td>
                                    <td className="py-2 px-3 font-mono align-top">
                                        {renderTimeRanges(item.fruehling_ranges, item.fruehling)}
                                    </td>
                                    <td className="py-2 px-3 font-mono align-top">
                                        {renderTimeRanges(item.sommer_ranges, item.sommer)}
                                    </td>
                                    <td className="py-2 px-3 font-mono align-top">
                                        {renderTimeRanges(item.herbst_ranges, item.herbst)}
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
                                                recordType="hlzf"
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
                                                isOpen={openMenuId === `hlzf-${item.id}`}
                                                onOpenChange={(isOpen) =>
                                                    { onMenuOpenChange(isOpen ? `hlzf-${item.id}` : null); }
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
                <p className="text-muted-foreground text-center py-8">No HLZF data available</p>
            )}
        </Card>
    );
}
