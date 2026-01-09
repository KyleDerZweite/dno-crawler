/**
 * EditDNODialog - Dialog for editing DNO metadata
 */

import { useState, useEffect } from "react";
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

interface EditDNOData {
    name: string;
    region: string;
    website: string;
    description: string;
    phone: string;
    email: string;
    contact_address: string;
}

interface EditDNODialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    dnoName: string;
    initialData: EditDNOData;
    onSave: (data: EditDNOData) => void;
    isPending: boolean;
}

export function EditDNODialog({
    open,
    onOpenChange,
    dnoName,
    initialData,
    onSave,
    isPending,
}: EditDNODialogProps) {
    const [formData, setFormData] = useState<EditDNOData>(initialData);

    // Reset form when dialog opens
    useEffect(() => {
        if (open) {
            setFormData(initialData);
        }
    }, [open, initialData]);

    const handleChange = (field: keyof EditDNOData, value: string) => {
        setFormData((prev) => ({ ...prev, [field]: value }));
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Edit DNO</DialogTitle>
                    <DialogDescription>Update metadata for {dnoName}</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <label className="text-sm font-medium">Name</label>
                        <Input
                            type="text"
                            value={formData.name}
                            onChange={(e) => { handleChange("name", e.target.value); }}
                        />
                    </div>
                    <div className="grid gap-2">
                        <label className="text-sm font-medium">Region</label>
                        <Input
                            type="text"
                            value={formData.region}
                            onChange={(e) => { handleChange("region", e.target.value); }}
                        />
                    </div>
                    <div className="grid gap-2">
                        <label className="text-sm font-medium">Website</label>
                        <Input
                            type="url"
                            value={formData.website}
                            onChange={(e) => { handleChange("website", e.target.value); }}
                        />
                    </div>
                    <div className="grid gap-2">
                        <label className="text-sm font-medium">Description</label>
                        <Input
                            type="text"
                            value={formData.description}
                            onChange={(e) => { handleChange("description", e.target.value); }}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="grid gap-2">
                            <label className="text-sm font-medium">Phone</label>
                            <Input
                                type="text"
                                value={formData.phone}
                                onChange={(e) => { handleChange("phone", e.target.value); }}
                            />
                        </div>
                        <div className="grid gap-2">
                            <label className="text-sm font-medium">Email</label>
                            <Input
                                type="email"
                                value={formData.email}
                                onChange={(e) => { handleChange("email", e.target.value); }}
                            />
                        </div>
                    </div>
                    <div className="grid gap-2">
                        <label className="text-sm font-medium">Contact Address</label>
                        <Input
                            type="text"
                            value={formData.contact_address}
                            onChange={(e) => { handleChange("contact_address", e.target.value); }}
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => { onOpenChange(false); }}>
                        Cancel
                    </Button>
                    <Button onClick={() => { onSave(formData); }} disabled={isPending}>
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
