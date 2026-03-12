/**
 * EditRecordDialog - Dialog for editing Netzentgelte or HLZF records
 *
 * HLZF seasons are stored as JSON arrays [{start, end}].
 * The edit form uses text inputs for convenience (e.g. "08:00-20:00, 21:00-23:00")
 * and converts to/from structured arrays on save/load.
 */

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import type { HLZFTimeRange } from "@/types";

interface NetzentgelteEditData {
    id: number;
    leistung?: number;
    arbeit?: number;
}

interface HLZFEditData {
    id: number;
    winter?: string;
    fruehling?: string;
    sommer?: string;
    herbst?: string;
}

export type { NetzentgelteEditData, HLZFEditData };

/** Convert JSON array to display string for editing: "08:00:00-20:00:00, 21:00:00-23:00:00" */
export function rangesToString(ranges: HLZFTimeRange[] | null | undefined): string {
    if (!ranges || ranges.length === 0) return "";
    return ranges.map(r => `${r.start}-${r.end}`).join(", ");
}

/** Parse display string back to JSON array */
export function stringToRanges(text: string): HLZFTimeRange[] | null {
    const trimmed = text.trim();
    if (!trimmed) return null;
    const ranges: HLZFTimeRange[] = [];
    const parts = trimmed.split(/[,;\n]+/);
    for (const part of parts) {
        const match = part.trim().match(/^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(\d{1,2}:\d{2}(?::\d{2})?)$/);
        if (match) {
            const start = match[1].split(":").length === 2 ? match[1] + ":00" : match[1];
            const end = match[2].split(":").length === 2 ? match[2] + ":00" : match[2];
            // Zero-pad hours
            const padTime = (t: string) => {
                const [h, ...rest] = t.split(":");
                return [h.padStart(2, "0"), ...rest].join(":");
            };
            ranges.push({ start: padTime(start), end: padTime(end) });
        }
    }
    return ranges.length > 0 ? ranges : null;
}

interface EditRecordDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    recordType: "netzentgelte" | "hlzf";
    editData: NetzentgelteEditData | HLZFEditData | null;
    onDataChange: (data: NetzentgelteEditData | HLZFEditData) => void;
    onSave: () => void;
    isPending: boolean;
}

export function EditRecordDialog({
    open,
    onOpenChange,
    recordType,
    editData,
    onDataChange,
    onSave,
    isPending,
}: EditRecordDialogProps) {
    if (!editData) return null;

    const isNetzentgelte = recordType === "netzentgelte";
    const netzData = editData as NetzentgelteEditData;
    const hlzfData = editData as HLZFEditData;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>
                        Edit {isNetzentgelte ? "Netzentgelte" : "HLZF"} Record
                    </DialogTitle>
                    <DialogDescription>
                        Update the values for this record.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    {isNetzentgelte ? (
                        <>
                            <div className="grid gap-2">
                                <label className="text-sm font-medium">Leistung (€/kW)</label>
                                <Input
                                    type="number"
                                    step="0.01"
                                    value={netzData.leistung ?? ""}
                                    onChange={(e) =>
                                        { onDataChange({
                                            ...netzData,
                                            leistung: e.target.value ? parseFloat(e.target.value) : undefined,
                                        }); }
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label className="text-sm font-medium">Arbeit (ct/kWh)</label>
                                <Input
                                    type="number"
                                    step="0.001"
                                    value={netzData.arbeit ?? ""}
                                    onChange={(e) =>
                                        { onDataChange({
                                            ...netzData,
                                            arbeit: e.target.value ? parseFloat(e.target.value) : undefined,
                                        }); }
                                    }
                                />
                            </div>
                        </>
                    ) : (
                        <>
                            <p className="text-xs text-muted-foreground">
                                Format: HH:MM-HH:MM (comma-separated for multiple windows)
                            </p>
                            <div className="grid gap-2">
                                <label htmlFor="hlzf-winter" className="text-sm font-medium">
                                    Winter
                                </label>
                                <Input
                                    id="hlzf-winter"
                                    type="text"
                                    placeholder="e.g., 08:00-20:00, 21:00-23:00"
                                    value={hlzfData.winter ?? ""}
                                    onChange={(e) =>
                                        { onDataChange({ ...hlzfData, winter: e.target.value }); }
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label htmlFor="hlzf-fruehling" className="text-sm font-medium">
                                    Frühling
                                </label>
                                <Input
                                    id="hlzf-fruehling"
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.fruehling ?? ""}
                                    onChange={(e) =>
                                        { onDataChange({ ...hlzfData, fruehling: e.target.value }); }
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label htmlFor="hlzf-sommer" className="text-sm font-medium">
                                    Sommer
                                </label>
                                <Input
                                    id="hlzf-sommer"
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.sommer ?? ""}
                                    onChange={(e) =>
                                        { onDataChange({ ...hlzfData, sommer: e.target.value }); }
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label htmlFor="hlzf-herbst" className="text-sm font-medium">
                                    Herbst
                                </label>
                                <Input
                                    id="hlzf-herbst"
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.herbst ?? ""}
                                    onChange={(e) =>
                                        { onDataChange({ ...hlzfData, herbst: e.target.value }); }
                                    }
                                />
                            </div>
                        </>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => { onOpenChange(false); }}>
                        Cancel
                    </Button>
                    <Button onClick={onSave} disabled={isPending}>
                        {isPending ? (
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
    );
}
