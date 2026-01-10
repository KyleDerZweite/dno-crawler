/**
 * Custom hook for data filtering state management
 */

import { useState, useMemo, useEffect, useCallback } from "react";
import type { Netzentgelte, HLZF } from "@/lib/api";
import { isValidValue } from "../utils/data-utils";

interface FilterOptions {
    years: number[];
    voltageLevels: string[];
}

interface UseDataFiltersOptions {
    netzentgelte: Netzentgelte[];
    hlzf: HLZF[];
}

/**
 * Hook that manages year and voltage level filter state
 */
export function useDataFilters({ netzentgelte, hlzf }: UseDataFiltersOptions) {
    const [yearFilter, setYearFilter] = useState<number[]>([]);
    const [yearFilterInitialized, setYearFilterInitialized] = useState(false);
    const [voltageLevelFilter, setVoltageLevelFilter] = useState<string[]>([]);

    // Calculate available filter options from data
    // Only include voltage levels that have actual data (not just "-" values)
    const filterOptions: FilterOptions = useMemo(() => {
        const years = new Set<number>();
        const voltageLevels = new Set<string>();

        netzentgelte.forEach((item) => {
            years.add(item.year);
            // Only add voltage level if it has at least one real value
            const hasData = isValidValue(item.leistung) ||
                isValidValue(item.arbeit) ||
                isValidValue(item.leistung_unter_2500h) ||
                isValidValue(item.arbeit_unter_2500h);
            if (item.voltage_level && hasData) {
                voltageLevels.add(item.voltage_level);
            }
        });
        hlzf.forEach((item) => {
            years.add(item.year);
            // Only add voltage level if it has at least one real value
            const hasData = isValidValue(item.winter) ||
                isValidValue(item.herbst) ||
                isValidValue(item.fruehling) ||
                isValidValue(item.sommer);
            if (item.voltage_level && hasData) {
                voltageLevels.add(item.voltage_level);
            }
        });

        return {
            years: Array.from(years).sort((a, b) => b - a),
            voltageLevels: Array.from(voltageLevels).sort(),
        };
    }, [netzentgelte, hlzf]);

    // Set initial year filter based on available data
    useEffect(() => {
        if (yearFilterInitialized || filterOptions.years.length === 0) return;

        const availableYears = filterOptions.years;
        let defaultYear: number;

        if (availableYears.includes(2024)) {
            defaultYear = 2024;
        } else if (availableYears.length === 1) {
            defaultYear = availableYears[0];
        } else {
            defaultYear = availableYears[0];
        }

        setYearFilter([defaultYear]);
        setYearFilterInitialized(true);
    }, [filterOptions.years, yearFilterInitialized]);

    // Toggle year filter
    const toggleYearFilter = useCallback((year: number) => {
        setYearFilter((prev) =>
            prev.includes(year)
                ? prev.filter((y) => y !== year)
                : [...prev, year]
        );
    }, []);

    // Toggle voltage level filter
    const toggleVoltageLevelFilter = useCallback((level: string) => {
        setVoltageLevelFilter((prev) =>
            prev.includes(level)
                ? prev.filter((l) => l !== level)
                : [...prev, level]
        );
    }, []);

    // Clear all filters
    const clearFilters = useCallback(() => {
        setYearFilter([]);
        setVoltageLevelFilter([]);
    }, []);

    // Apply filters to netzentgelte
    // Also filter out records with no actual data (all values are "-" or null)
    const filteredNetzentgelte = useMemo(() => {
        return netzentgelte.filter((item) => {
            if (yearFilter.length > 0 && !yearFilter.includes(item.year)) return false;
            if (voltageLevelFilter.length > 0 && !voltageLevelFilter.includes(item.voltage_level))
                return false;
            // Exclude records with no actual data
            const hasData = isValidValue(item.leistung) ||
                isValidValue(item.arbeit) ||
                isValidValue(item.leistung_unter_2500h) ||
                isValidValue(item.arbeit_unter_2500h);
            return hasData;
        });
    }, [netzentgelte, yearFilter, voltageLevelFilter]);

    // Apply filters to HLZF
    // Also filter out records with no actual data (all values are "-" or null)
    const filteredHLZF = useMemo(() => {
        return hlzf.filter((item) => {
            if (yearFilter.length > 0 && !yearFilter.includes(item.year)) return false;
            if (voltageLevelFilter.length > 0 && !voltageLevelFilter.includes(item.voltage_level))
                return false;
            // Exclude records with no actual data
            const hasData = isValidValue(item.winter) ||
                isValidValue(item.herbst) ||
                isValidValue(item.fruehling) ||
                isValidValue(item.sommer);
            return hasData;
        });
    }, [hlzf, yearFilter, voltageLevelFilter]);

    return {
        // State
        yearFilter,
        voltageLevelFilter,
        filterOptions,

        // Actions
        toggleYearFilter,
        toggleVoltageLevelFilter,
        clearFilters,
        setYearFilter,
        setVoltageLevelFilter,

        // Filtered data
        filteredNetzentgelte,
        filteredHLZF,

        // Status
        hasActiveFilters: yearFilter.length > 0 || voltageLevelFilter.length > 0,
    };
}
