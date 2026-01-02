import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import {
    Sparkles,
    Globe,
    FileText,
    Pencil,
    HelpCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

type ExtractionSource = "ai" | "html_parser" | "pdf_regex" | "manual" | null | undefined;
type SourceFormat = "html" | "pdf" | null | undefined;

export interface ExtractionSourceBadgeProps {
    source?: ExtractionSource;
    model?: string | null;
    sourceFormat?: SourceFormat;
    lastEditedBy?: string | null;
    lastEditedAt?: string | null;
    compact?: boolean;
}

/**
 * Badge component that shows the extraction source of a data record.
 * Displays different icons/colors for AI, HTML parser, PDF regex, or manual edits.
 */
export function ExtractionSourceBadge({
    source,
    model,
    sourceFormat,
    lastEditedBy,
    lastEditedAt,
    compact = false,
}: ExtractionSourceBadgeProps) {
    // Format date for tooltip
    const formatDate = (dateStr?: string | null) => {
        if (!dateStr) return "";
        return new Date(dateStr).toLocaleDateString("de-DE", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    // Get display config based on source type
    const getSourceDisplay = () => {
        switch (source) {
            case "ai":
                return {
                    icon: <Sparkles className="h-3.5 w-3.5" />,
                    label: "AI",
                    className: "text-purple-600 bg-purple-50 border-purple-200 dark:bg-purple-900/20 dark:border-purple-800 dark:text-purple-400",
                    description: model
                        ? `Extracted by AI: ${model}`
                        : "Extracted by AI",
                };
            case "html_parser":
                return {
                    icon: <Globe className="h-3.5 w-3.5" />,
                    label: "HTML",
                    className: "text-blue-600 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-400",
                    description: "Extracted from HTML via parser",
                };
            case "pdf_regex":
                return {
                    icon: <FileText className="h-3.5 w-3.5" />,
                    label: "PDF",
                    className: "text-orange-600 bg-orange-50 border-orange-200 dark:bg-orange-900/20 dark:border-orange-800 dark:text-orange-400",
                    description: "Extracted from PDF via regex",
                };
            case "manual":
                return {
                    icon: <Pencil className="h-3.5 w-3.5" />,
                    label: "Manual",
                    className: "text-green-600 bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800 dark:text-green-400",
                    description: lastEditedBy
                        ? `Manually edited by ${lastEditedBy}${lastEditedAt ? ` on ${formatDate(lastEditedAt)}` : ""}`
                        : "Manually edited",
                };
            default:
                return {
                    icon: <HelpCircle className="h-3.5 w-3.5" />,
                    label: "Unknown",
                    className: "text-gray-500 bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-700 dark:text-gray-400",
                    description: "Source unknown (legacy data)",
                };
        }
    };

    const display = getSourceDisplay();

    // Build detailed tooltip content
    const tooltipContent = () => {
        const lines: string[] = [display.description];

        // Add source format if available and relevant
        if (source && source !== "manual" && sourceFormat) {
            lines.push(`Format: ${sourceFormat.toUpperCase()}`);
        }

        return (
            <div className="space-y-1 text-xs">
                {lines.map((line, i) => (
                    <div key={i}>{line}</div>
                ))}
            </div>
        );
    };

    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Badge
                        variant="outline"
                        className={cn(
                            "gap-1 font-normal cursor-default text-xs py-0.5 px-1.5",
                            display.className
                        )}
                    >
                        {display.icon}
                        {!compact && <span>{display.label}</span>}
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    {tooltipContent()}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}
