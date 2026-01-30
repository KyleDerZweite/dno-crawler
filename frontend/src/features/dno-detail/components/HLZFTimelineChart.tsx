/**
 * HLZFTimelineChart - Range bar chart for HLZF peak load time windows
 * Features: Single year view (default) or Multi-year comparison mode
 */

import { useMemo, useState, useEffect } from "react";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { Clock, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { HLZF, HLZFTimeRange } from "@/lib/api";
import { useChartColors } from "../hooks/use-chart-colors";
import { ChartColorPicker } from "./ChartColorPicker";
import { getApexChartBase, VOLTAGE_LEVELS } from "../utils/chart-colors";

interface HLZFTimelineChartProps {
    hlzf: HLZF[];
    isLoading?: boolean;
    className?: string;
}

type ViewMode = "single" | "compare";

const SEASONS = [
    { key: "winter" as const, label: "Winter", rangeKey: "winter_ranges" as const },
    { key: "fruehling" as const, label: "Frühling", rangeKey: "fruehling_ranges" as const },
    { key: "sommer" as const, label: "Sommer", rangeKey: "sommer_ranges" as const },
    { key: "herbst" as const, label: "Herbst", rangeKey: "herbst_ranges" as const },
];

const DUMMY_DATE = "1970-01-01";

function parseTimeToTimestamp(timeStr: string): number {
    const clean = timeStr.trim();
    const [hours, minutes] = clean.split(":").map(Number);
    return new Date(`${DUMMY_DATE}T${String(hours).padStart(2, "0")}:${String(minutes || 0).padStart(2, "0")}:00`).getTime();
}

function parseRawTimeString(raw: string | null | undefined): HLZFTimeRange[] {
    if (!raw || raw === "-" || raw.trim() === "") return [];
    const ranges: HLZFTimeRange[] = [];
    const parts = raw.split(/[,;]|und|&/i);
    for (const part of parts) {
        const match = part.match(/(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})/);
        if (match) {
            ranges.push({ start: match[1] + ":00", end: match[2] + ":00" });
        }
    }
    return ranges;
}

function hexToRgba(hex: string, alpha: number): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function HLZFTimelineChart({ hlzf, isLoading, className }: HLZFTimelineChartProps) {
    const chartColors = useChartColors("hlzf-timeline");
    const [viewMode, setViewMode] = useState<ViewMode>("single");
    const [singleDropdownOpen, setSingleDropdownOpen] = useState(false);
    const [compareDropdownOpen, setCompareDropdownOpen] = useState(false);

    // Get available years (descending)
    const availableYears = useMemo(() => {
        const yearSet = new Set<number>();
        hlzf.forEach((item) => yearSet.add(item.year));
        return Array.from(yearSet).sort((a, b) => b - a);
    }, [hlzf]);

    // Single mode: one selected year
    const [singleYear, setSingleYear] = useState<number>(() => availableYears[0] || new Date().getFullYear());

    // Compare mode: multiple selected years
    const [compareYears, setCompareYears] = useState<number[]>(() =>
        availableYears.length > 0 ? [availableYears[0]] : []
    );

    // Sync singleYear when availableYears changes
    useEffect(() => {
        if (availableYears.length > 0 && !availableYears.includes(singleYear)) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setSingleYear(availableYears[0]);
        }
    }, [availableYears, singleYear]);

    // Active years based on mode
    const selectedYears = useMemo(() =>
        viewMode === "single" ? [singleYear] : compareYears,
        [viewMode, singleYear, compareYears]
    );
    const primaryYear = Math.max(...selectedYears);

    const toggleCompareYear = (year: number) => {
        setCompareYears(prev =>
            prev.includes(year)
                ? prev.filter(y => y !== year)
                : [...prev, year]
        );
    };

    // Get voltage levels across selected years
    const voltageLevels = useMemo(() => {
        const levels = new Set<string>();
        hlzf
            .filter((h) => selectedYears.includes(h.year))
            .forEach((h) => levels.add(h.voltage_level));

        return Array.from(levels).sort((a, b) => {
            const idxA = VOLTAGE_LEVELS.indexOf(a as typeof VOLTAGE_LEVELS[number]);
            const idxB = VOLTAGE_LEVELS.indexOf(b as typeof VOLTAGE_LEVELS[number]);
            return idxA - idxB;
        });
    }, [hlzf, selectedYears]);

    // Build series
    const series = useMemo(() => {
        const sortedYears = [...selectedYears].sort((a, b) => b - a);
        const allSeries: ApexAxisChartSeries = [];

        for (const year of sortedYears) {
            const yearData = hlzf.filter((h) => h.year === year);

            for (const level of voltageLevels) {
                const levelData = yearData.find((h) => h.voltage_level === level);
                const data: { x: string; y: [number, number] }[] = [];

                if (levelData) {
                    for (const season of SEASONS) {
                        let ranges = levelData[season.rangeKey] as HLZFTimeRange[] | undefined;
                        if (!ranges || ranges.length === 0) {
                            const rawValue = levelData[season.key] as string | undefined;
                            ranges = parseRawTimeString(rawValue);
                        }

                        for (const range of ranges) {
                            try {
                                const start = parseTimeToTimestamp(range.start);
                                const end = parseTimeToTimestamp(range.end);
                                if (!isNaN(start) && !isNaN(end)) {
                                    data.push({ x: season.label, y: [start, end] });
                                }
                            } catch { /* skip */ }
                        }
                    }
                }

                if (data.length > 0) {
                    allSeries.push({
                        name: viewMode === "compare" && selectedYears.length > 1
                            ? `${level} (${year})`
                            : level,
                        data,
                    });
                }
            }
        }

        return allSeries;
    }, [hlzf, selectedYears, voltageLevels, viewMode]);

    // Build colors with opacity for comparison years
    const seriesColors = useMemo(() => {
        const sortedYears = [...selectedYears].sort((a, b) => b - a);
        const colors: string[] = [];

        for (const year of sortedYears) {
            const isPrimary = year === primaryYear;
            const opacity = isPrimary ? 1 : 0.4;

            for (const level of voltageLevels) {
                const colorIdx = VOLTAGE_LEVELS.indexOf(level as typeof VOLTAGE_LEVELS[number]);
                const baseColor = chartColors.preset.colors[colorIdx >= 0 ? colorIdx : 0];

                const yearData = hlzf.filter((h) => h.year === year);
                const levelData = yearData.find((h) => h.voltage_level === level);
                const hasData = levelData && SEASONS.some(season => {
                    const ranges = levelData[season.rangeKey] as HLZFTimeRange[] | undefined;
                    const raw = levelData[season.key] as string | undefined;
                    return (ranges && ranges.length > 0) || parseRawTimeString(raw).length > 0;
                });

                if (hasData) {
                    colors.push(isPrimary ? baseColor : hexToRgba(baseColor, opacity));
                }
            }
        }

        return colors;
    }, [selectedYears, voltageLevels, primaryYear, chartColors.preset.colors, hlzf]);

    // ApexCharts options
    const options: ApexOptions = useMemo(() => {
        const base = getApexChartBase(chartColors.preset);
        const minTime = new Date(`${DUMMY_DATE}T00:00:00`).getTime();
        const maxTime = new Date(`${DUMMY_DATE}T23:59:59`).getTime();

        return {
            ...base,
            chart: { ...base.chart, type: "rangeBar", height: 280 },
            colors: seriesColors,
            plotOptions: {
                bar: { horizontal: true, barHeight: "85%", rangeBarGroupRows: false },
            },
            xaxis: {
                type: "datetime",
                min: minTime,
                max: maxTime,
                labels: {
                    datetimeUTC: false,
                    format: "HH:mm",
                    style: { colors: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280" },
                },
                axisBorder: { show: false },
                axisTicks: { show: false },
            },
            yaxis: {
                labels: {
                    style: { colors: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280" },
                },
            },
            tooltip: { ...base.tooltip, x: { format: "HH:mm" } },
            legend: { ...base.legend, show: true, position: "bottom", onItemClick: { toggleDataSeries: true } },
            noData: {
                text: "No HLZF data available",
                style: { color: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280" },
            },
        };
    }, [chartColors.preset, seriesColors]);

    if (isLoading) {
        return (
            <div className={cn("flex h-[280px] items-center justify-center", className)}>
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
        );
    }

    const hasData = series.length > 0;

    return (
        <div className={className}>
            {/* Header */}
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold">HLZF Timeline</h3>
                </div>
                <div className="flex items-center gap-2">
                    {/* Mode toggle */}
                    <div className="flex rounded-md border">
                        <Button
                            variant={viewMode === "single" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setViewMode("single")}
                            className="h-7 rounded-r-none text-xs"
                        >
                            Single
                        </Button>
                        <Button
                            variant={viewMode === "compare" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setViewMode("compare")}
                            className="h-7 rounded-l-none text-xs"
                        >
                            Compare
                        </Button>
                    </div>

                    {/* Year selector - changes based on mode */}
                    {viewMode === "single" ? (
                        <div className="relative">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setSingleDropdownOpen(!singleDropdownOpen)}
                                className="h-8 min-w-[80px] justify-between text-sm"
                            >
                                {singleYear}
                            </Button>
                            {singleDropdownOpen && (
                                <div className="absolute right-0 top-full z-[100] mt-1 w-32 rounded-md border bg-popover p-1 shadow-lg">
                                    {availableYears.map((year) => (
                                        <button
                                            key={year}
                                            onClick={() => {
                                                setSingleYear(year);
                                                setSingleDropdownOpen(false);
                                            }}
                                            className={cn(
                                                "flex w-full items-center rounded px-3 py-1.5 text-sm hover:bg-accent",
                                                singleYear === year && "bg-accent font-medium"
                                            )}
                                        >
                                            {year}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="relative">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCompareDropdownOpen(!compareDropdownOpen)}
                                className="h-8 min-w-[100px] justify-between text-sm"
                            >
                                {compareYears.length === 0
                                    ? "Select years"
                                    : compareYears.length === 1
                                        ? compareYears[0]
                                        : `${compareYears.length} years`}
                            </Button>
                            {compareDropdownOpen && (
                                <div className="absolute right-0 top-full z-[100] mt-1 w-40 rounded-md border bg-popover p-1 shadow-lg">
                                    {availableYears.map((year) => (
                                        <button
                                            key={year}
                                            onClick={() => toggleCompareYear(year)}
                                            className={cn(
                                                "flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent",
                                                compareYears.includes(year) && "bg-accent"
                                            )}
                                        >
                                            <div className={cn(
                                                "h-4 w-4 rounded border flex items-center justify-center",
                                                compareYears.includes(year)
                                                    ? "bg-primary border-primary text-primary-foreground"
                                                    : "border-input"
                                            )}>
                                                {compareYears.includes(year) && <Check className="h-3 w-3" />}
                                            </div>
                                            {year}
                                            {year === primaryYear && compareYears.length > 1 && (
                                                <span className="ml-auto text-[10px] text-muted-foreground">primary</span>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Color picker */}
                    <ChartColorPicker
                        preset={chartColors.preset}
                        seriesNames={voltageLevels}
                        onColorChange={chartColors.setColor}
                        onThemeChange={chartColors.setTheme}
                        onBackgroundChange={chartColors.setBackground}
                        onExport={chartColors.exportString}
                        onImport={chartColors.importString}
                        onReset={chartColors.resetToDefault}
                        onApplyPreset={(key) => chartColors.applyPreset(key as string)}
                    />
                </div>
            </div>

            {/* Chart */}
            <div style={{ background: chartColors.preset.background }} className="rounded-lg">
                {hasData ? (
                    <Chart options={options} series={series} type="rangeBar" height={280} />
                ) : (
                    <div className="flex h-[280px] items-center justify-center text-muted-foreground">
                        {viewMode === "compare" && compareYears.length === 0
                            ? "Select at least one year"
                            : "No HLZF data available"}
                    </div>
                )}
            </div>
        </div>
    );
}
