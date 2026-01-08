/**
 * CrawlDialog - Dialog for triggering crawl jobs
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { RefreshCw, Loader2, Check, ChevronUp, ChevronDown, Info } from "lucide-react";
import { cn } from "@/lib/utils";

// Available years for crawling
const AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022];
const DEFAULT_CRAWL_YEARS = [2025, 2024];

interface CrawlDialogProps {
    dnoName: string;
    crawlable: boolean;
    hasLocalFiles: boolean;
    onTrigger: (params: {
        years: number[];
        dataType: "all" | "netzentgelte" | "hlzf";
        jobType: "full" | "crawl" | "extract";
    }) => void;
    isPending: boolean;
}

export function CrawlDialog({
    dnoName,
    crawlable,
    hasLocalFiles,
    onTrigger,
    isPending,
}: CrawlDialogProps) {
    const [open, setOpen] = useState(false);
    const [crawlYears, setCrawlYears] = useState<number[]>(DEFAULT_CRAWL_YEARS);
    const [crawlDataType, setCrawlDataType] = useState<"all" | "netzentgelte" | "hlzf">("all");
    const [crawlJobType, setCrawlJobType] = useState<"full" | "crawl" | "extract">("full");
    const [showAdvanced, setShowAdvanced] = useState(false);

    const toggleCrawlYear = (year: number) => {
        setCrawlYears((prev) => {
            if (prev.includes(year)) {
                if (prev.length === 1) return prev; // keep at least one
                return prev.filter((y) => y !== year);
            }
            return [...prev, year].sort((a, b) => b - a);
        });
    };

    const crawlJobCount = crawlYears.length * (crawlDataType === "all" ? 2 : 1);

    const handleTrigger = () => {
        onTrigger({
            years: crawlYears,
            dataType: crawlDataType,
            jobType: crawlJobType,
        });
        setOpen(false);
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button disabled={!crawlable && !hasLocalFiles}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Trigger Crawl
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Trigger Crawl for {dnoName}</DialogTitle>
                    <DialogDescription>
                        Select years and data types to crawl. One job will be created per year.
                    </DialogDescription>
                </DialogHeader>

                {/* Year Selection */}
                <div className="space-y-3">
                    <label className="text-sm font-medium">Years to crawl</label>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_YEARS.map((year) => {
                            const isSelected = crawlYears.includes(year);
                            return (
                                <button
                                    key={year}
                                    type="button"
                                    onClick={() => toggleCrawlYear(year)}
                                    className={cn(
                                        "flex items-center gap-2 px-3 py-2 rounded-md border text-sm font-medium transition-colors",
                                        isSelected
                                            ? "bg-primary text-primary-foreground border-primary"
                                            : "bg-background border-input hover:bg-muted"
                                    )}
                                >
                                    <div
                                        className={cn(
                                            "w-4 h-4 rounded border flex items-center justify-center",
                                            isSelected
                                                ? "bg-primary-foreground/20 border-primary-foreground/50"
                                                : "border-current opacity-50"
                                        )}
                                    >
                                        {isSelected && <Check className="w-3 h-3" />}
                                    </div>
                                    {year}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Advanced Options */}
                <div className="border rounded-lg overflow-hidden">
                    <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-sm"
                    >
                        <span className="font-medium">Advanced Options</span>
                        {showAdvanced ? (
                            <ChevronUp className="w-4 h-4 text-muted-foreground" />
                        ) : (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                        )}
                    </button>
                    {showAdvanced && (
                        <div className="p-3 border-t space-y-4">
                            {/* Job Type Selection */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Job Type</label>
                                <div className="flex flex-wrap gap-2">
                                    {(
                                        [
                                            { value: "full", label: "Full Pipeline", desc: "Crawl + Extract" },
                                            { value: "crawl", label: "Crawl Only", desc: "Download file" },
                                            { value: "extract", label: "Extract Only", desc: "Process existing file" },
                                        ] as const
                                    ).map((opt) => (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            onClick={() => setCrawlJobType(opt.value)}
                                            className={cn(
                                                "flex flex-col items-start px-3 py-2 rounded-md border text-sm transition-colors",
                                                crawlJobType === opt.value
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-background border-input hover:bg-muted"
                                            )}
                                        >
                                            <span className="font-medium">{opt.label}</span>
                                            <span
                                                className={cn(
                                                    "text-xs",
                                                    crawlJobType === opt.value
                                                        ? "text-primary-foreground/70"
                                                        : "text-muted-foreground"
                                                )}
                                            >
                                                {opt.desc}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                                {crawlJobType === "extract" && (
                                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                                        <Info className="w-3 h-3" />
                                        Requires an existing downloaded file for the selected year/type
                                    </p>
                                )}
                            </div>

                            {/* Data Type Selection */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Data Type</label>
                                <div className="flex gap-2">
                                    {(["all", "netzentgelte", "hlzf"] as const).map((type) => (
                                        <button
                                            key={type}
                                            type="button"
                                            onClick={() => setCrawlDataType(type)}
                                            className={cn(
                                                "px-3 py-1.5 rounded-md border text-sm font-medium transition-colors",
                                                crawlDataType === type
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-background border-input hover:bg-muted"
                                            )}
                                        >
                                            {type === "all" ? "All" : type === "netzentgelte" ? "Netzentgelte" : "HLZF"}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter className="gap-2 sm:gap-0">
                    <Button variant="outline" onClick={() => setOpen(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleTrigger} disabled={isPending || crawlYears.length === 0}>
                        {isPending ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Creating jobs...
                            </>
                        ) : (
                            <>
                                Start {crawlJobCount}{" "}
                                {crawlJobType === "full" ? "" : crawlJobType + " "}
                                Job{crawlJobCount > 1 ? "s" : ""}
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
