/**
 * Custom hook for calculating data completeness metrics
 */

import { useMemo } from "react";
import type { Netzentgelte, HLZF } from "@/lib/api";
import { isValidValue } from "../utils/data-utils";

interface DataCompletenessResult {
    total: number;
    expected: number;
    percentage: number;
    netzentgelte: {
        valid: number;
        expected: number;
        percentage: number;
    };
    hlzf: {
        valid: number;
        expected: number;
        percentage: number;
    };
    years: number;
    voltageLevels: number;
}

interface UseDataCompletenessOptions {
    netzentgelte: Netzentgelte[];
    hlzf: HLZF[];
}

/**
 * Calculate data completeness metrics for a DNO
 * 
 * Uses a 50/50 weighted average:
 * - 50% weight for Netzentgelte
 * - 50% weight for HLZF
 */
export function useDataCompleteness({
    netzentgelte,
    hlzf,
}: UseDataCompletenessOptions): DataCompletenessResult {
    return useMemo(() => {
        // Get unique years that have any data
        const allYears = new Set<number>();
        netzentgelte.forEach((item) => allYears.add(item.year));
        hlzf.forEach((item) => allYears.add(item.year));
        const yearsCount = Math.max(3, allYears.size || 0);

        // Determine voltage levels this DNO actually has data for
        // Only count a voltage level if it has at least one real value (not just "-")
        const netzentgelteVoltageLevels = new Set<string>();
        netzentgelte.forEach((item) => {
            const hasLeistung = isValidValue(item.leistung);
            const hasArbeit = isValidValue(item.arbeit);
            const hasLeistungUnter = isValidValue(item.leistung_unter_2500h);
            const hasArbeitUnter = isValidValue(item.arbeit_unter_2500h);
            if (hasLeistung || hasArbeit || hasLeistungUnter || hasArbeitUnter) {
                netzentgelteVoltageLevels.add(item.voltage_level);
            }
        });

        const hlzfVoltageLevels = new Set<string>();
        hlzf.forEach((item) => {
            const hasWinter = isValidValue(item.winter);
            const hasHerbst = isValidValue(item.herbst);
            const hasFruehling = isValidValue(item.fruehling);
            const hasSommer = isValidValue(item.sommer);
            if (hasWinter || hasHerbst || hasFruehling || hasSommer) {
                hlzfVoltageLevels.add(item.voltage_level);
            }
        });

        // Combine voltage levels from both data types
        const allVoltageLevels = new Set([...netzentgelteVoltageLevels, ...hlzfVoltageLevels]);

        // If no data yet, assume standard 5 levels for expected
        const levelsCount = allVoltageLevels.size || 5;

        // Expected = levels × years for each data type
        const expectedPerType = levelsCount * yearsCount;

        // Count Netzentgelte records with actual price data
        // Only count records for voltage levels that exist in this DNO
        let netzentgelteValid = 0;
        netzentgelte.forEach((item) => {
            // Only count if this voltage level is valid for this DNO
            if (!netzentgelteVoltageLevels.has(item.voltage_level) && allVoltageLevels.size > 0) {
                return; // Skip voltage levels that don't exist for this DNO
            }
            const hasLeistung = isValidValue(item.leistung);
            const hasArbeit = isValidValue(item.arbeit);
            const hasLeistungUnter = isValidValue(item.leistung_unter_2500h);
            const hasArbeitUnter = isValidValue(item.arbeit_unter_2500h);
            if (hasLeistung || hasArbeit || hasLeistungUnter || hasArbeitUnter) {
                netzentgelteValid++;
            }
        });

        // Count HLZF records with actual time data
        // Only count records for voltage levels that exist in this DNO
        let hlzfValid = 0;
        hlzf.forEach((item) => {
            // Only count if this voltage level is valid for this DNO
            if (!hlzfVoltageLevels.has(item.voltage_level) && allVoltageLevels.size > 0) {
                return; // Skip voltage levels that don't exist for this DNO
            }
            const hasWinter = isValidValue(item.winter);
            const hasHerbst = isValidValue(item.herbst);
            const hasFruehling = isValidValue(item.fruehling);
            const hasSommer = isValidValue(item.sommer);
            if (hasWinter || hasHerbst || hasFruehling || hasSommer) {
                hlzfValid++;
            }
        });

        // Calculate percentages for each type (capped at 100%)
        const netzentgeltePercent =
            expectedPerType > 0
                ? Math.min((netzentgelteValid / expectedPerType) * 100, 100)
                : 0;
        const hlzfPercent =
            expectedPerType > 0 ? Math.min((hlzfValid / expectedPerType) * 100, 100) : 0;

        // Weighted average: 50% Netzentgelte + 50% HLZF
        const totalPercent = (netzentgeltePercent + hlzfPercent) / 2;

        return {
            total: netzentgelteValid + hlzfValid,
            expected: expectedPerType * 2,
            percentage: totalPercent,
            netzentgelte: {
                valid: netzentgelteValid,
                expected: expectedPerType,
                percentage: netzentgeltePercent,
            },
            hlzf: {
                valid: hlzfValid,
                expected: expectedPerType,
                percentage: hlzfPercent,
            },
            years: yearsCount,
            voltageLevels: levelsCount,
        };
    }, [netzentgelte, hlzf]);
}
