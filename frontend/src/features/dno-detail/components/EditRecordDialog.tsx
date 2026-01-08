/**
 * EditRecordDialog - Dialog for editing Netzentgelte or HLZF records
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
                                        onDataChange({
                                            ...netzData,
                                            leistung: e.target.value ? parseFloat(e.target.value) : undefined,
                                        })
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
                                        onDataChange({
                                            ...netzData,
                                            arbeit: e.target.value ? parseFloat(e.target.value) : undefined,
                                        })
                                    }
                                />
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="grid gap-2">
                                <label className="text-sm font-medium">Winter</label>
                                <Input
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.winter ?? ""}
                                    onChange={(e) =>
                                        onDataChange({ ...hlzfData, winter: e.target.value })
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label className="text-sm font-medium">Frühling</label>
                                <Input
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.fruehling ?? ""}
                                    onChange={(e) =>
                                        onDataChange({ ...hlzfData, fruehling: e.target.value })
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label className="text-sm font-medium">Sommer</label>
                                <Input
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.sommer ?? ""}
                                    onChange={(e) =>
                                        onDataChange({ ...hlzfData, sommer: e.target.value })
                                    }
                                />
                            </div>
                            <div className="grid gap-2">
                                <label className="text-sm font-medium">Herbst</label>
                                <Input
                                    type="text"
                                    placeholder="e.g., 08:00-20:00"
                                    value={hlzfData.herbst ?? ""}
                                    onChange={(e) =>
                                        onDataChange({ ...hlzfData, herbst: e.target.value })
                                    }
                                />
                            </div>
                        </>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
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
