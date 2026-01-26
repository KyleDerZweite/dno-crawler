/**
 * Chart Color Utilities
 * Presets and parser for chart color customization system
 */

export interface ChartColorPreset {
    name: string;
    theme: "dark" | "light";
    background: string;
    colors: string[];
}

// Default voltage level order for consistent color mapping
export const VOLTAGE_LEVELS = ["HS", "HS/MS", "MS", "MS/NS", "NS"] as const;

// Built-in presets
export const DEFAULT_PRESETS: Record<string, ChartColorPreset> = {
    DARK_NEON: {
        name: "Dark Neon",
        theme: "dark",
        background: "#1e1e1e",
        colors: ["#775DD0", "#00E396", "#FEB019", "#FF4560", "#008FFB"],
    },
    DARK_EMERALD: {
        name: "Dark Emerald",
        theme: "dark",
        background: "#0f172a",
        colors: ["#34d399", "#06b6d4", "#f59e0b", "#ef4444", "#8b5cf6"],
    },
    LIGHT_CORPORATE: {
        name: "Corporate Light",
        theme: "light",
        background: "#ffffff",
        colors: ["#2563EB", "#059669", "#D97706", "#DC2626", "#475569"],
    },
    LIGHT_PASTEL: {
        name: "Pastel Light",
        theme: "light",
        background: "#fafafa",
        colors: ["#818cf8", "#4ade80", "#fbbf24", "#f87171", "#60a5fa"],
    },
    COLORBLIND: {
        name: "Colorblind Friendly",
        theme: "dark",
        background: "#1e1e1e",
        colors: ["#0077BB", "#33BBEE", "#EE7733", "#CC3311", "#009988"],
    },
};

/**
 * Parse preset string format: "theme|background|color1,color2,color3..."
 * Example: "dark|#1e1e1e|#775DD0,#00E396,#FEB019,#FF4560,#008FFB"
 */
export function parsePresetString(str: string): ChartColorPreset | null {
    try {
        const parts = str.trim().split("|");
        if (parts.length !== 3) return null;

        const [theme, background, colorStr] = parts;
        if (theme !== "dark" && theme !== "light") return null;

        const colors = colorStr.split(",").map((c) => c.trim());
        if (colors.length === 0 || !colors.every((c) => /^#[0-9A-Fa-f]{6}$/.test(c))) {
            return null;
        }

        return {
            name: "Custom",
            theme,
            background,
            colors,
        };
    } catch {
        return null;
    }
}

/**
 * Export preset to string format for sharing
 */
export function exportPresetString(preset: ChartColorPreset): string {
    return `${preset.theme}|${preset.background}|${preset.colors.join(",")}`;
}

/**
 * Get color for a specific voltage level from preset
 */
export function getVoltageColor(preset: ChartColorPreset, voltageLevel: string): string {
    const index = VOLTAGE_LEVELS.indexOf(voltageLevel as typeof VOLTAGE_LEVELS[number]);
    return preset.colors[index >= 0 ? index : 0] || preset.colors[0];
}

/**
 * Get ApexCharts theme options from preset
 */
export function getApexTheme(preset: ChartColorPreset) {
    return {
        mode: preset.theme,
        palette: "palette1",
    };
}

/**
 * Get common ApexCharts options for dark/light theme
 */
export function getApexChartBase(preset: ChartColorPreset) {
    const isDark = preset.theme === "dark";
    return {
        chart: {
            background: preset.background,
            foreColor: isDark ? "#e5e7eb" : "#374151",
            toolbar: {
                show: true,
                tools: {
                    download: true,
                    selection: true,
                    zoom: true,
                    zoomin: true,
                    zoomout: true,
                    pan: true,
                    reset: true,
                },
                export: {
                    csv: { filename: "chart-data" },
                    svg: { filename: "chart" },
                    png: { filename: "chart" },
                },
            },
        },
        theme: getApexTheme(preset),
        grid: {
            borderColor: isDark ? "#374151" : "#e5e7eb",
            strokeDashArray: 3,
        },
        tooltip: {
            theme: preset.theme,
        },
        legend: {
            position: "bottom" as const,
            onItemClick: { toggleDataSeries: true },
            labels: {
                colors: isDark ? "#e5e7eb" : "#374151",
            },
        },
    };
}
