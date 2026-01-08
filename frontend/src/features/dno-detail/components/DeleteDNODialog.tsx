/**
 * DeleteDNODialog - Confirmation dialog for DNO deletion
 */

import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { AlertCircle, Loader2, Trash2 } from "lucide-react";

interface DeleteDNODialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    dnoName: string;
    onConfirm: () => void;
    isPending: boolean;
}

export function DeleteDNODialog({
    open,
    onOpenChange,
    dnoName,
    onConfirm,
    isPending,
}: DeleteDNODialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-destructive">Delete DNO</DialogTitle>
                    <DialogDescription>
                        Are you sure you want to permanently delete <strong>{dnoName}</strong>?
                    </DialogDescription>
                </DialogHeader>
                <div className="py-4">
                    <div className="flex items-start gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                        <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
                        <div className="text-sm text-destructive">
                            <p className="font-medium">This action cannot be undone!</p>
                            <p className="mt-1 opacity-80">
                                All associated data will be permanently deleted:
                            </p>
                            <ul className="list-disc list-inside mt-1 opacity-80">
                                <li>All Netzentgelte records</li>
                                <li>All HLZF records</li>
                                <li>All crawl jobs and history</li>
                                <li>All cached files</li>
                                <li>All locations linked to this DNO</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={onConfirm}
                        disabled={isPending}
                    >
                        {isPending ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Deleting...
                            </>
                        ) : (
                            <>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete Forever
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
