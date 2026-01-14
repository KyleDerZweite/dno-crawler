import { useState, useMemo, Fragment } from "react";
import { Link } from "react-router-dom";
import { Zap, Clock, ArrowRight, AlertCircle, Globe } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { CheckCircle2, AlertTriangle, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PublicSearchNetzentgelte, PublicSearchHLZF } from "@/lib/api";

interface DataPreviewTablesProps {
    netzentgelte?: PublicSearchNetzentgelte[];
    hlzf?: PublicSearchHLZF[];
    dnoId?: number;
    dnoSlug?: string;
    showManageLink?: boolean;
}

/**
 * Read-only verification status badge for preview tables
 */
function ReadOnlyVerificationBadge({ status }: { status?: string }) {
    const getStatusDisplay = () => {
        switch (status) {
            case "verified":
                return {
                    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
                    label: "Verified",
                    className: "text-green-600 bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800",
                };
            case "flagged":
                return {
                    icon: <AlertTriangle className="h-3.5 w-3.5" />,
                    label: "Flagged",
                    className: "text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800",
                };
            default:
                return {
                    icon: <Circle className="h-3.5 w-3.5" />,
                    label: "Unverified",
                    className: "text-gray-500 bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-700",
                };
        }
    };

    const display = getStatusDisplay();

    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger asChild>
                    <div
                        className={cn(
                            "inline-flex items-center justify-center gap-1 px-1.5 py-0.5 rounded border cursor-default",
                            display.className
                        )}
                    >
                        {display.icon}
                    </div>
                </TooltipTrigger>
                <TooltipContent>{display.label}</TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}

/**
 * Selectable time component - click to select the time value
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
            style={{ userSelect: 'text' }}
        >
            {value}
        </span>
    );
}

/**
 * Render time ranges from parsed backend array
 * Each time is independently selectable
 */
function renderTimeRanges(
    ranges: { start: string; end: string }[] | null | undefined,
    rawValue: string | null | undefined
): React.ReactNode {
    // Use parsed ranges if available
    if (ranges && ranges.length > 0) {
        return (
            <div className="space-y-0.5" style={{ userSelect: 'none' }}>
                {ranges.map((range, idx) => (
                    <div key={idx} className="text-sm whitespace-nowrap flex items-center">
                        <SelectableTime value={range.start} />
                        <span className="text-muted-foreground px-1" style={{ userSelect: 'none' }}>–</span>
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

/**
 * DataPreviewTables: Read-only data tables for search results
 * Matches DNODetailPage formatting with select-all for copy and HH:MM:00 formatting.
 * No edit/delete actions - links to DNO page for management.
 */
export function DataPreviewTables({
    netzentgelte,
    hlzf,
    dnoId,
    dnoSlug,
    showManageLink = true,
}: DataPreviewTablesProps) {
    const [decimalFormat, setDecimalFormat] = useState<'DE' | 'US'>('DE');
    const hasNetzentgelte = netzentgelte && netzentgelte.length > 0;
    const hasHlzf = hlzf && hlzf.length > 0;
    const hasData = hasNetzentgelte || hasHlzf;

    // Get link destination (prefer ID over slug for reliable routing)
    const dnoLink = dnoId ? `/dnos/${dnoId}` : dnoSlug ? `/dnos/${dnoSlug}` : null;

    const formatNumber = (val: number | undefined | null, decimals: number) => {
        if (val === undefined || val === null) return "-";
        
        return val.toLocaleString(decimalFormat === 'DE' ? 'de-DE' : 'en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    };

    // Group Netzentgelte by year
    const groupedNetzentgelte = useMemo(() => {
        if (!netzentgelte) return {};
        const groups: Record<number, PublicSearchNetzentgelte[]> = {};
        netzentgelte.forEach((item) => {
            if (!groups[item.year]) groups[item.year] = [];
            groups[item.year].push(item);
        });
        // Sort items within each group by voltage level
        Object.values(groups).forEach(group => {
            group.sort((a, b) => a.voltage_level.localeCompare(b.voltage_level));
        });
        return groups;
    }, [netzentgelte]);

    const sortedNetzentgelteYears = useMemo(() => {
        return Object.keys(groupedNetzentgelte)
            .map(Number)
            .sort((a, b) => b - a);
    }, [groupedNetzentgelte]);

    // Group HLZF by year
    const groupedHlzf = useMemo(() => {
        if (!hlzf) return {};
        const groups: Record<number, PublicSearchHLZF[]> = {};
        hlzf.forEach((item) => {
            if (!groups[item.year]) groups[item.year] = [];
            groups[item.year].push(item);
        });
        // Sort items within each group by voltage level
        Object.values(groups).forEach(group => {
            group.sort((a, b) => a.voltage_level.localeCompare(b.voltage_level));
        });
        return groups;
    }, [hlzf]);

    const sortedHlzfYears = useMemo(() => {
        return Object.keys(groupedHlzf)
            .map(Number)
            .sort((a, b) => b - a);
    }, [groupedHlzf]);


    if (!hasData) {
        return (
            <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>No data available for the selected years.</AlertDescription>
            </Alert>
        );
    }

    return (
        <div className="space-y-6 w-full">
            {/* Netzentgelte Table - matches DNODetailPage layout */}
            {hasNetzentgelte && (
                <Card className="p-8">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <Zap className="h-5 w-5 text-blue-500" />
                            Netzentgelte
                        </h2>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 gap-2 text-xs"
                            onClick={() => setDecimalFormat(prev => prev === 'DE' ? 'US' : 'DE')}
                            title={`Switch to ${decimalFormat === 'DE' ? 'US (Dot)' : 'German (Comma)'} format`}
                        >
                            <Globe className="h-3.5 w-3.5" />
                            {decimalFormat === 'DE' ? '1.234,56' : '1,234.56'}
                        </Button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b">
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" rowSpan={2}>Voltage Level</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50" colSpan={2}>{"≥ 2.500 h/a"}</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50" colSpan={2}>{"< 2.500 h/a"}</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground border-l border-border/50" rowSpan={2}>Status</th>
                                </tr>
                                <tr className="border-b text-xs">
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground border-l border-border/50">Leistung (€/kW)</th>
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground">Arbeit (ct/kWh)</th>
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground border-l border-border/50">Leistung (€/kW)</th>
                                    <th className="text-right py-1 px-3 font-normal text-muted-foreground">Arbeit (ct/kWh)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedNetzentgelteYears.map((year) => (
                                    <Fragment key={year}>
                                        <tr className="bg-muted/30">
                                            <td colSpan={6} className="py-2 px-3 font-semibold text-muted-foreground border-y border-border/50">
                                                {year}
                                            </td>
                                        </tr>
                                        {groupedNetzentgelte[year].map((item, index) => {
                                            const itemWithExtras = item as PublicSearchNetzentgelte & {
                                                leistung_unter_2500h?: number;
                                                arbeit_unter_2500h?: number;
                                                verification_status?: string;
                                            };
                                            return (
                                                <tr key={index} className="border-b border-border/50 hover:bg-muted/50">
                                                    <td className="py-2 px-3 font-medium">{item.voltage_level}</td>
                                                    <td className="py-2 px-3 text-right font-mono border-l border-border/50">
                                                        <span className="select-all">{formatNumber(item.leistung, 2)}</span>
                                                    </td>
                                                    <td className="py-2 px-3 text-right font-mono">
                                                        <span className="select-all">{formatNumber(item.arbeit, 3)}</span>
                                                    </td>
                                                    <td className="py-2 px-3 text-right font-mono border-l border-border/50">
                                                        <span className="select-all">
                                                            {itemWithExtras.leistung_unter_2500h ? formatNumber(itemWithExtras.leistung_unter_2500h, 2) : formatNumber(item.leistung, 2)}
                                                        </span>
                                                    </td>
                                                    <td className="py-2 px-3 text-right font-mono">
                                                        <span className="select-all">
                                                            {itemWithExtras.arbeit_unter_2500h ? formatNumber(itemWithExtras.arbeit_unter_2500h, 3) : formatNumber(item.arbeit, 3)}
                                                        </span>
                                                    </td>
                                                    <td className="py-2 px-3 text-center border-l border-border/50">
                                                        <ReadOnlyVerificationBadge status={itemWithExtras.verification_status} />
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </Fragment>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}

            {/* HLZF Table - matches DNODetailPage layout with time formatting */}
            {hasHlzf && (
                <Card className="p-8">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Clock className="h-5 w-5 text-purple-500" />
                        HLZF (Hochlastzeitfenster)
                    </h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b">
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground w-20">Voltage Level</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Winter</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Frühling</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Sommer</th>
                                    <th className="text-left py-2 px-3 font-medium text-muted-foreground" style={{ width: '16%' }}>Herbst</th>
                                    <th className="text-center py-2 px-3 font-medium text-muted-foreground w-24">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedHlzfYears.map((year) => (
                                    <Fragment key={year}>
                                        <tr className="bg-muted/30">
                                            <td colSpan={6} className="py-2 px-3 font-semibold text-muted-foreground border-y border-border/50">
                                                {year}
                                            </td>
                                        </tr>
                                        {groupedHlzf[year].map((item, index) => {
                                            const itemWithStatus = item as PublicSearchHLZF & { verification_status?: string };
                                            return (
                                                <tr key={index} className="border-b border-border/50 hover:bg-muted/50">
                                                    <td className="py-2 px-3 font-medium">{item.voltage_level}</td>
                                                    <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.winter_ranges, item.winter)}</td>
                                                    <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.fruehling_ranges, item.fruehling)}</td>
                                                    <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.sommer_ranges, item.sommer)}</td>
                                                    <td className="py-2 px-3 font-mono align-top">{renderTimeRanges(item.herbst_ranges, item.herbst)}</td>
                                                    <td className="py-2 px-3 text-center">
                                                        <ReadOnlyVerificationBadge status={itemWithStatus.verification_status} />
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </Fragment>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}

            {/* Manage Link with Flag Notice */}
            {showManageLink && dnoLink && (
                <div className="space-y-3 pt-2">
                    <p className="text-sm text-muted-foreground text-center">
                        If any data is incorrect, please visit the DNO page to flag it for admin review.
                    </p>
                    <Button asChild className="w-full gap-2">
                        <Link to={dnoLink}>
                            View Full Details & Manage Data
                            <ArrowRight className="w-4 h-4" />
                        </Link>
                    </Button>
                </div>
            )}
        </div>
    );
}