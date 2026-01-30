/**
 * PriceTrendChart - Line chart for Netzentgelte price trends
 * Features: solid lines for history, dashed for forecast, export, legend toggle
 */

import { useMemo, useState } from "react";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { Button } from "@/components/ui/button";
import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Netzentgelte } from "@/lib/api";
import { useChartColors } from "../hooks/use-chart-colors";
import { ChartColorPicker } from "./ChartColorPicker";
import { getApexChartBase, VOLTAGE_LEVELS } from "../utils/chart-colors";

interface PriceTrendChartProps {
    netzentgelte: Netzentgelte[];
    isLoading?: boolean;
    className?: string;
}

type PriceField = "arbeit" | "leistung";

const CURRENT_YEAR = new Date().getFullYear();

export function PriceTrendChart({ netzentgelte, isLoading, className }: PriceTrendChartProps) {
    const [priceField, setPriceField] = useState<PriceField>("arbeit");
    const chartColors = useChartColors("price-trend");

    // Extract unique years and voltage levels from data
    const { years, voltageLevels } = useMemo(() => {
        const yearSet = new Set<number>();
        const levelSet = new Set<string>();

        netzentgelte.forEach((item) => {
            yearSet.add(item.year);
            levelSet.add(item.voltage_level);
        });

        // Sort years ascending
        const years = Array.from(yearSet).sort((a, b) => a - b);

        // Sort voltage levels in standard order
        const voltageLevels = Array.from(levelSet).sort((a, b) => {
            const idxA = VOLTAGE_LEVELS.indexOf(a as typeof VOLTAGE_LEVELS[number]);
            const idxB = VOLTAGE_LEVELS.indexOf(b as typeof VOLTAGE_LEVELS[number]);
            return idxA - idxB;
        });

        return { years, voltageLevels };
    }, [netzentgelte]);

    // Build series data - split into actual and forecast
    // For now, forecast is any year > current year (placeholder)
    const { series, dashArray } = useMemo(() => {
        const series: ApexAxisChartSeries = [];
        const dashArray: number[] = [];

        voltageLevels.forEach((level) => {
            // Data for this voltage level
            const levelData = netzentgelte.filter((n) => n.voltage_level === level);

            // Actual data (solid line)
            const actualData = years.map((year) => {
                if (year > CURRENT_YEAR) return null; // No actual data for future
                const record = levelData.find((n) => n.year === year);
                return record?.[priceField] ?? null;
            });

            // Forecast data (dashed line) - overlaps at current year for continuity
            const forecastData = years.map((year) => {
                if (year < CURRENT_YEAR) return null; // No forecast for past
                const record = levelData.find((n) => n.year === year);
                return record?.[priceField] ?? null;
            });

            // Check if we have any forecast data
            const hasForecast = forecastData.some((v) => v !== null && years.some((y) => y > CURRENT_YEAR));

            // Add actual series
            series.push({
                name: level,
                data: actualData,
            });
            dashArray.push(0); // Solid

            // Add forecast series only if there's future data
            if (hasForecast) {
                series.push({
                    name: `${level} (Forecast)`,
                    data: forecastData,
                });
                dashArray.push(5); // Dashed
            }
        });

        return { series, dashArray };
    }, [netzentgelte, years, voltageLevels, priceField]);

    // ApexCharts options
    const options: ApexOptions = useMemo(() => {
        const base = getApexChartBase(chartColors.preset);

        // Build colors array matching series order
        const colors: string[] = [];
        voltageLevels.forEach((level, idx) => {
            const color = chartColors.preset.colors[idx] || chartColors.preset.colors[0];
            colors.push(color);
            // If there's a forecast series, use same color
            const hasForecast = series.some((s) => s.name === `${level} (Forecast)`);
            if (hasForecast) {
                colors.push(color);
            }
        });

        return {
            ...base,
            chart: {
                ...base.chart,
                type: "line",
                height: 300,
                animations: {
                    enabled: true,
                    easing: "easeinout",
                    speed: 500,
                },
            },
            colors,
            stroke: {
                curve: "smooth",
                width: 3,
                dashArray,
            },
            xaxis: {
                categories: years.map(String),
                axisBorder: { show: false },
                axisTicks: { show: false },
                labels: {
                    style: {
                        colors: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280",
                    },
                },
            },
            yaxis: {
                title: {
                    text: priceField === "arbeit" ? "ct/kWh" : "€/kW",
                    style: {
                        color: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280",
                    },
                },
                labels: {
                    formatter: (val) => (val !== null ? val.toFixed(2) : ""),
                    style: {
                        colors: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280",
                    },
                },
            },
            markers: {
                size: 4,
                hover: { size: 6 },
            },
            legend: {
                ...base.legend,
                showForSingleSeries: true,
            },
            noData: {
                text: "No price data available",
                style: {
                    color: chartColors.preset.theme === "dark" ? "#9ca3af" : "#6b7280",
                },
            },
        };
    }, [chartColors.preset, years, voltageLevels, priceField, dashArray, series]);

    if (isLoading) {
        return (
            <div className={cn("flex h-[300px] items-center justify-center", className)}>
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
        );
    }

    return (
        <div className={className}>
            {/* Header */}
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold">Price Trends</h3>
                </div>
                <div className="flex items-center gap-2">
                    {/* Price field toggle */}
                    <div className="flex rounded-md border">
                        <Button
                            variant={priceField === "arbeit" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setPriceField("arbeit")}
                            className="h-7 rounded-r-none text-xs"
                        >
                            Arbeit (ct/kWh)
                        </Button>
                        <Button
                            variant={priceField === "leistung" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setPriceField("leistung")}
                            className="h-7 rounded-l-none text-xs"
                        >
                            Leistung (€/kW)
                        </Button>
                    </div>
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
            <div
                style={{ background: chartColors.preset.background }}
                className="rounded-lg"
            >
                <Chart
                    options={options}
                    series={series}
                    type="line"
                    height={300}
                />
            </div>
        </div>
    );
}
