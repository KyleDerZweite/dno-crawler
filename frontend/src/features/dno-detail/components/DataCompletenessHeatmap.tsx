/**
 * DataCompletenessHeatmap - Heatmap showing record counts by type/year/voltage
 * Features: explicit neutral color for 0, green gradient for 1+, tooltip
 */

import { useMemo } from "react";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { Grid3X3 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Netzentgelte, HLZF } from "@/lib/api";
import { useChartColors } from "../hooks/use-chart-colors";
import { ChartColorPicker } from "./ChartColorPicker";
import { getApexChartBase, VOLTAGE_LEVELS } from "../utils/chart-colors";

interface DataCompletenessHeatmapProps {
    netzentgelte: Netzentgelte[];
    hlzf: HLZF[];
    isLoading?: boolean;
    className?: string;
}

export function DataCompletenessHeatmap({
    netzentgelte,
    hlzf,
    isLoading,
    className,
}: DataCompletenessHeatmapProps) {
    const chartColors = useChartColors("data-completeness");

    // Get all years from both data types
    const years = useMemo(() => {
        const yearSet = new Set<number>();
        netzentgelte.forEach((n) => yearSet.add(n.year));
        hlzf.forEach((h) => yearSet.add(h.year));
        return Array.from(yearSet).sort((a, b) => a - b);
    }, [netzentgelte, hlzf]);

    // Get all voltage levels from both data types
    const voltageLevels = useMemo(() => {
        const levels = new Set<string>();
        netzentgelte.forEach((n) => levels.add(n.voltage_level));
        hlzf.forEach((h) => levels.add(h.voltage_level));

        return Array.from(levels).sort((a, b) => {
            const idxA = VOLTAGE_LEVELS.indexOf(a as typeof VOLTAGE_LEVELS[number]);
            const idxB = VOLTAGE_LEVELS.indexOf(b as typeof VOLTAGE_LEVELS[number]);
            return idxA - idxB;
        });
    }, [netzentgelte, hlzf]);

    // Build heatmap series
    // Each row is a voltage level, each cell shows combined count of HLZF + Netzentgelte
    // Reverse order so HS is at top, NS at bottom (ApexCharts renders first series at bottom)
    const series = useMemo(() => {
        const result: ApexAxisChartSeries = [];

        // Reverse: iterate NS -> HS so HS ends up at top
        const reversedLevels = [...voltageLevels].reverse();
        for (const level of reversedLevels) {
            const data = years.map((year) => {
                const netzCount = netzentgelte.filter(
                    (n) => n.year === year && n.voltage_level === level
                ).length;
                const hlzfCount = hlzf.filter(
                    (h) => h.year === year && h.voltage_level === level
                ).length;
                return netzCount + hlzfCount;
            });
            result.push({
                name: level,
                data,
            });
        }

        return result;
    }, [netzentgelte, hlzf, years, voltageLevels]);

    // ApexCharts options
    const options: ApexOptions = useMemo(() => {
        const base = getApexChartBase(chartColors.preset);
        const isDark = chartColors.preset.theme === "dark";

        // Find max value for color scale
        const maxCount = Math.max(
            1,
            ...series.flatMap((s) => (s.data as number[]) || [])
        );

        return {
            ...base,
            chart: {
                ...base.chart,
                type: "heatmap",
                height: Math.max(200, series.length * 32),
                toolbar: {
                    show: true,
                    tools: {
                        download: true,
                        selection: false,
                        zoom: false,
                        zoomin: false,
                        zoomout: false,
                        pan: false,
                        reset: false,
                    },
                },
            },
            dataLabels: {
                enabled: true,
                style: {
                    colors: [isDark ? "#fff" : "#000"],
                },
            },
            plotOptions: {
                heatmap: {
                    shadeIntensity: 0.5,
                    colorScale: {
                        ranges: [
                            {
                                from: 0,
                                to: 0,
                                color: isDark ? "#2d2d2d" : "#e5e7eb",
                                name: "No Data",
                            },
                            {
                                from: 1,
                                to: Math.ceil(maxCount / 3),
                                color: "#22c55e",
                                name: "Low",
                            },
                            {
                                from: Math.ceil(maxCount / 3) + 1,
                                to: Math.ceil((maxCount * 2) / 3),
                                color: "#16a34a",
                                name: "Medium",
                            },
                            {
                                from: Math.ceil((maxCount * 2) / 3) + 1,
                                to: maxCount + 10,
                                color: "#15803d",
                                name: "High",
                            },
                        ],
                    },
                },
            },
            xaxis: {
                categories: years.map(String),
                labels: {
                    style: {
                        colors: isDark ? "#9ca3af" : "#6b7280",
                    },
                },
            },
            yaxis: {
                labels: {
                    style: {
                        colors: isDark ? "#9ca3af" : "#6b7280",
                    },
                },
            },
            tooltip: {
                ...base.tooltip,
                y: {
                    formatter: (val: number) => `${val} record${val !== 1 ? "s" : ""}`,
                },
            },
            legend: {
                show: false,
            },
            noData: {
                text: "No data available",
                style: {
                    color: isDark ? "#9ca3af" : "#6b7280",
                },
            },
        };
    }, [chartColors.preset, years, series]);

    if (isLoading) {
        return (
            <div className={cn("flex h-[200px] items-center justify-center", className)}>
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
        );
    }

    return (
        <div className={className}>
            {/* Header */}
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Grid3X3 className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold">Data Completeness</h3>
                </div>
                <div className="flex items-center gap-2">
                    {/* Legend */}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <div className="flex items-center gap-1">
                            <div
                                className="h-3 w-3 rounded"
                                style={{ background: chartColors.preset.theme === "dark" ? "#2d2d2d" : "#e5e7eb" }}
                            />
                            <span>0</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="h-3 w-3 rounded bg-green-500" />
                            <span>1+</span>
                        </div>
                    </div>
                    {/* Color picker */}
                    <ChartColorPicker
                        preset={chartColors.preset}
                        seriesNames={[]}
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
            <div
                style={{ background: chartColors.preset.background }}
                className="rounded-lg"
            >
                {series.length > 0 && years.length > 0 ? (
                    <Chart
                        options={options}
                        series={series}
                        type="heatmap"
                        height={Math.max(200, series.length * 32)}
                    />
                ) : (
                    <div className="flex h-[200px] items-center justify-center text-muted-foreground">
                        No data available
                    </div>
                )}
            </div>
        </div>
    );
}
