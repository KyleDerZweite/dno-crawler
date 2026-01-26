/**
 * useChartColors Hook
 * Manages chart color state with localStorage persistence
 */

import { useState, useCallback, useMemo } from "react";
import type { ChartColorPreset } from "../utils/chart-colors";
import {
    DEFAULT_PRESETS,
    parsePresetString,
    exportPresetString,
} from "../utils/chart-colors";

const STORAGE_PREFIX = "chart-colors-";

interface UseChartColorsResult {
    preset: ChartColorPreset;
    setPreset: (preset: ChartColorPreset) => void;
    setColor: (index: number, color: string) => void;
    setTheme: (theme: "dark" | "light") => void;
    setBackground: (color: string) => void;
    exportString: () => string;
    importString: (str: string) => boolean;
    resetToDefault: () => void;
    applyPreset: (presetKey: keyof typeof DEFAULT_PRESETS) => void;
    availablePresets: typeof DEFAULT_PRESETS;
}

export function useChartColors(chartId: string): UseChartColorsResult {
    // Load from localStorage or use default
    const loadInitial = (): ChartColorPreset => {
        try {
            const stored = localStorage.getItem(STORAGE_PREFIX + chartId);
            if (stored) {
                const parsed = parsePresetString(stored);
                if (parsed) return parsed;
            }
        } catch {
            // Ignore localStorage errors
        }
        return DEFAULT_PRESETS.DARK_NEON;
    };

    const [preset, setPresetState] = useState<ChartColorPreset>(loadInitial);

    // Persist to localStorage on change
    const setPreset = useCallback(
        (newPreset: ChartColorPreset) => {
            setPresetState(newPreset);
            try {
                localStorage.setItem(STORAGE_PREFIX + chartId, exportPresetString(newPreset));
            } catch {
                // Ignore localStorage errors
            }
        },
        [chartId]
    );

    const setColor = useCallback(
        (index: number, color: string) => {
            const newColors = [...preset.colors];
            newColors[index] = color;
            setPreset({ ...preset, colors: newColors });
        },
        [preset, setPreset]
    );

    const setTheme = useCallback(
        (theme: "dark" | "light") => {
            // Also update background to match theme
            const newBg = theme === "dark" ? "#1e1e1e" : "#ffffff";
            setPreset({ ...preset, theme, background: newBg });
        },
        [preset, setPreset]
    );

    const setBackground = useCallback(
        (color: string) => {
            setPreset({ ...preset, background: color });
        },
        [preset, setPreset]
    );

    const exportString = useCallback(() => {
        return exportPresetString(preset);
    }, [preset]);

    const importString = useCallback(
        (str: string): boolean => {
            const parsed = parsePresetString(str);
            if (parsed) {
                setPreset(parsed);
                return true;
            }
            return false;
        },
        [setPreset]
    );

    const resetToDefault = useCallback(() => {
        setPreset(DEFAULT_PRESETS.DARK_NEON);
    }, [setPreset]);

    const applyPreset = useCallback(
        (presetKey: keyof typeof DEFAULT_PRESETS) => {
            setPreset(DEFAULT_PRESETS[presetKey]);
        },
        [setPreset]
    );

    const availablePresets = useMemo(() => DEFAULT_PRESETS, []);

    return {
        preset,
        setPreset,
        setColor,
        setTheme,
        setBackground,
        exportString,
        importString,
        resetToDefault,
        applyPreset,
        availablePresets,
    };
}
