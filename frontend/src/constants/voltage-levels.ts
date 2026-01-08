/**
 * Voltage level constants.
 * 
 * Standard German grid voltage levels used across the application.
 */

// Valid voltage levels in order from highest to lowest
export const VOLTAGE_LEVELS = ["HS", "HS/MS", "MS", "MS/NS", "NS"] as const;

// Type for voltage level
export type VoltageLevel = (typeof VOLTAGE_LEVELS)[number];

// Display labels for voltage levels
export const VOLTAGE_LEVEL_LABELS: Record<VoltageLevel, string> = {
    HS: "Hochspannung",
    "HS/MS": "Hochspannung / Mittelspannung",
    MS: "Mittelspannung",
    "MS/NS": "Mittelspannung / Niederspannung",
    NS: "Niederspannung",
};

// Short labels for compact display
export const VOLTAGE_LEVEL_SHORT_LABELS: Record<VoltageLevel, string> = {
    HS: "HS",
    "HS/MS": "HS/MS",
    MS: "MS",
    "MS/NS": "MS/NS",
    NS: "NS",
};

// Check if a string is a valid voltage level
export function isValidVoltageLevel(value: string): value is VoltageLevel {
    return VOLTAGE_LEVELS.includes(value as VoltageLevel);
}
