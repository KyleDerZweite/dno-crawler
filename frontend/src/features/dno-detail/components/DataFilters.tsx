/**
 * DataFilters - Filter controls for year and voltage level
 */

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar, Zap, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DataFiltersProps {
    yearFilter: number[];
    voltageLevelFilter: string[];
    filterOptions: {
        years: number[];
        voltageLevels: string[];
    };
    onToggleYear: (year: number) => void;
    onToggleVoltageLevel: (level: string) => void;
    onClearFilters: () => void;
}

export function DataFilters({
    yearFilter,
    voltageLevelFilter,
    filterOptions,
    onToggleYear,
    onToggleVoltageLevel,
    onClearFilters,
}: DataFiltersProps) {
    const hasActiveFilters = yearFilter.length > 0 || voltageLevelFilter.length > 0;

    return (
        <div className="flex flex-col gap-4 p-4 bg-muted/30 rounded-lg border">
            {/* Year Filters */}
            <div className="space-y-2">
                <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Year</span>
                </div>
                <div className="flex flex-wrap gap-2">
                    {filterOptions.years.map((year) => {
                        const isSelected = yearFilter.includes(year);
                        return (
                            <button
                                key={year}
                                onClick={() => onToggleYear(year)}
                                className={cn(
                                    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                                    isSelected
                                        ? "bg-primary text-primary-foreground"
                                        : "bg-background border border-input hover:bg-muted"
                                )}
                            >
                                {year}
                            </button>
                        );
                    })}
                    {filterOptions.years.length === 0 && (
                        <span className="text-sm text-muted-foreground">No years available</span>
                    )}
                </div>
            </div>

            {/* Voltage Level Filters */}
            {filterOptions.voltageLevels.length > 0 && (
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Zap className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Voltage Level</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {filterOptions.voltageLevels.map((level) => {
                            const isSelected = voltageLevelFilter.includes(level);
                            return (
                                <button
                                    key={level}
                                    onClick={() => onToggleVoltageLevel(level)}
                                    className={cn(
                                        "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                                        isSelected
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-background border border-input hover:bg-muted"
                                    )}
                                >
                                    {level}
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Active Filters Summary & Clear */}
            {hasActiveFilters && (
                <div className="flex items-center justify-between pt-2 border-t">
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs text-muted-foreground">Active:</span>
                        {yearFilter.map((year) => (
                            <Badge key={year} variant="secondary" className="text-xs gap-1">
                                {year}
                                <button
                                    onClick={() => onToggleYear(year)}
                                    className="ml-1 hover:text-destructive"
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            </Badge>
                        ))}
                        {voltageLevelFilter.map((level) => (
                            <Badge key={level} variant="secondary" className="text-xs gap-1">
                                {level}
                                <button
                                    onClick={() => onToggleVoltageLevel(level)}
                                    className="ml-1 hover:text-destructive"
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            </Badge>
                        ))}
                    </div>
                    <Button variant="ghost" size="sm" onClick={onClearFilters}>
                        Clear all
                    </Button>
                </div>
            )}
        </div>
    );
}
