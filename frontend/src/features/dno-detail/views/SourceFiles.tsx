/**
 * SourceFiles View - File Upload and Listing
 * 
 * Fetches its own files data for lazy loading.
 */

import { useState, useRef } from "react";
import { useOutletContext } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, FolderInput, FileText, FileDown, Loader2, CheckCircle2, XCircle } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import type { DNODetailContext } from "./types";

export function SourceFiles() {
    const { numericId, dno } = useOutletContext<DNODetailContext>();
    const queryClient = useQueryClient();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadResults, setUploadResults] = useState<{ filename: string; success: boolean; message: string }[]>([]);

    const { data: filesResponse, isLoading } = useQuery({
        queryKey: ["dno-files", numericId],
        queryFn: () => api.dnos.getFiles(String(numericId)),
        enabled: !!numericId,
    });

    const files = filesResponse?.data || [];

    const handleFileUpload = async (filesList: FileList | null) => {
        if (!filesList || !numericId) return;
        setIsUploading(true);
        setUploadResults([]);
        const results: { filename: string; success: boolean; message: string }[] = [];

        for (const file of Array.from(filesList)) {
            try {
                const res = await api.dnos.uploadFile(String(numericId), file);
                results.push({
                    filename: file.name,
                    success: res.success,
                    message: res.message || (res.success ? "Uploaded" : "Failed")
                });
            } catch {
                results.push({ filename: file.name, success: false, message: "Error uploading" });
            }
        }

        setUploadResults(results);
        setIsUploading(false);
        queryClient.invalidateQueries({ queryKey: ["dno-files", numericId] });
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-4 animate-in fade-in duration-300">
            <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold">Source Documents</h2>
                <Button onClick={() => setUploadDialogOpen(true)}>
                    <Upload className="mr-2 h-4 w-4" /> Upload
                </Button>
            </div>

            <Card className="divide-y">
                {files.length === 0 ? (
                    <div className="p-12 text-center text-muted-foreground">
                        <FolderInput className="h-12 w-12 mx-auto mb-3 opacity-20" />
                        <p>No source files found.</p>
                        <p className="text-sm">Upload PDF or Excel files to extract data.</p>
                    </div>
                ) : (
                    files.map((file, i: number) => (
                        <div key={i} className="p-4 flex items-center justify-between hover:bg-muted/30">
                            <div className="flex items-center gap-4">
                                <div className="p-2 bg-orange-100 text-orange-600 rounded">
                                    <FileText className="h-5 w-5" />
                                </div>
                                <div>
                                    <p className="font-medium">{file.name}</p>
                                    <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</p>
                                </div>
                            </div>
                            <Button variant="ghost" size="sm" asChild>
                                <a href={`${import.meta.env.VITE_API_URL}${file.path}`} download={file.name}>
                                    <FileDown className="mr-2 h-4 w-4" /> Download
                                </a>
                            </Button>
                        </div>
                    ))
                )}
            </Card>

            {/* Upload Dialog */}
            <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Upload Files</DialogTitle>
                        <DialogDescription>
                            Upload PDF or Excel files for {dno.name}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            multiple
                            accept=".pdf,.xlsx,.xls"
                            onChange={(e) => handleFileUpload(e.target.files)}
                        />
                        <Button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isUploading}
                            className="w-full"
                        >
                            {isUploading ? (
                                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Uploading...</>
                            ) : (
                                <><Upload className="mr-2 h-4 w-4" /> Select Files</>
                            )}
                        </Button>

                        {uploadResults.length > 0 && (
                            <div className="mt-4 space-y-2">
                                {uploadResults.map((r, i) => (
                                    <div key={i} className="flex items-center gap-2 text-sm">
                                        {r.success ? (
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                        ) : (
                                            <XCircle className="h-4 w-4 text-red-500" />
                                        )}
                                        <span className="truncate">{r.filename}</span>
                                        <span className="text-muted-foreground text-xs ml-auto">{r.message}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
