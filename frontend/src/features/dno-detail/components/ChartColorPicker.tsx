/**
 * ChartColorPicker - Color customization panel for charts
 * Features: per-series color pickers, theme toggle, preset import/export
 */

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import {
    Palette,
    Copy,
    Check,
    Upload,
    Sun,
    Moon,
    RotateCcw,
    ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChartColorPreset } from "../utils/chart-colors";
import { DEFAULT_PRESETS, VOLTAGE_LEVELS } from "../utils/chart-colors";

interface ChartColorPickerProps {
    preset: ChartColorPreset;
    seriesNames?: string[];
    onColorChange: (index: number, color: string) => void;
    onThemeChange: (theme: "dark" | "light") => void;
    onBackgroundChange: (color: string) => void;
    onExport: () => string;
    onImport: (str: string) => boolean;
    onReset: () => void;
    onApplyPreset: (presetKey: string) => void;
    className?: string;
}

export function ChartColorPicker({
    preset,
    seriesNames = [...VOLTAGE_LEVELS],
    onColorChange,
    onThemeChange,
    onBackgroundChange,
    onExport,
    onImport,
    onReset,
    onApplyPreset,
    className,
}: ChartColorPickerProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [copied, setCopied] = useState(false);
    const [importValue, setImportValue] = useState("");
    const [importError, setImportError] = useState(false);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });

    // Update dropdown position when opened
    useEffect(() => {
        if (isOpen && buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            setDropdownPos({
                top: rect.bottom + 8,
                right: window.innerWidth - rect.right,
            });
        }
    }, [isOpen]);

    const handleCopy = () => {
        const str = onExport();
        navigator.clipboard.writeText(str);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleImport = () => {
        if (onImport(importValue)) {
            setImportValue("");
            setImportError(false);
        } else {
            setImportError(true);
        }
    };

    const handlePaste = async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (onImport(text)) {
                setImportError(false);
            } else {
                setImportError(true);
            }
        } catch {
            setImportError(true);
        }
    };

    return (
        <div className={cn("relative", className)}>
            <Button
                ref={buttonRef}
                variant="ghost"
                size="sm"
                onClick={() => setIsOpen(!isOpen)}
                className="gap-2"
            >
                <Palette className="h-4 w-4" />
                <ChevronDown className={cn("h-3 w-3 transition-transform", isOpen && "rotate-180")} />
            </Button>

            {isOpen && createPortal(
                <div
                    className="fixed w-80 rounded-lg border bg-popover p-4 shadow-xl"
                    style={{ top: dropdownPos.top, right: dropdownPos.right, zIndex: 9999 }}
                >
                    {/* Theme Toggle */}
                    <div className="mb-4 flex items-center justify-between">
                        <span className="text-sm font-medium">Theme</span>
                        <div className="flex gap-1">
                            <Button
                                variant={preset.theme === "dark" ? "default" : "outline"}
                                size="sm"
                                onClick={() => onThemeChange("dark")}
                                className="h-8 w-8 p-0"
                            >
                                <Moon className="h-4 w-4" />
                            </Button>
                            <Button
                                variant={preset.theme === "light" ? "default" : "outline"}
                                size="sm"
                                onClick={() => onThemeChange("light")}
                                className="h-8 w-8 p-0"
                            >
                                <Sun className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>

                    {/* Background Color */}
                    <div className="mb-4">
                        <label className="mb-1 block text-xs text-muted-foreground">Background</label>
                        <div className="flex items-center gap-2">
                            <input
                                type="color"
                                value={preset.background}
                                onChange={(e) => onBackgroundChange(e.target.value)}
                                className="h-8 w-10 cursor-pointer rounded border"
                            />
                            <input
                                type="text"
                                value={preset.background}
                                onChange={(e) => onBackgroundChange(e.target.value)}
                                className="h-8 flex-1 rounded border bg-background px-2 text-xs font-mono"
                            />
                        </div>
                    </div>

                    {/* Series Colors */}
                    <div className="mb-4">
                        <label className="mb-2 block text-xs text-muted-foreground">Series Colors</label>
                        <div className="space-y-2">
                            {seriesNames.slice(0, preset.colors.length).map((name, i) => (
                                <div key={name} className="flex items-center gap-2">
                                    <input
                                        type="color"
                                        value={preset.colors[i] || "#777777"}
                                        onChange={(e) => onColorChange(i, e.target.value)}
                                        className="h-6 w-8 cursor-pointer rounded border"
                                    />
                                    <span className="flex-1 text-sm">{name}</span>
                                    <span className="font-mono text-xs text-muted-foreground">
                                        {preset.colors[i]}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Presets */}
                    <div className="mb-4">
                        <label className="mb-2 block text-xs text-muted-foreground">Presets</label>
                        <div className="flex flex-wrap gap-1">
                            {Object.entries(DEFAULT_PRESETS).map(([key, p]) => (
                                <Button
                                    key={key}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => onApplyPreset(key)}
                                    className="h-7 text-xs"
                                    style={{
                                        borderColor: p.colors[0],
                                    }}
                                >
                                    {p.name}
                                </Button>
                            ))}
                        </div>
                    </div>

                    {/* Import/Export */}
                    <div className="mb-3 border-t pt-3">
                        <label className="mb-2 block text-xs text-muted-foreground">Share Preset</label>
                        <div className="flex gap-1">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleCopy}
                                className="flex-1 gap-1"
                            >
                                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                                {copied ? "Copied!" : "Copy"}
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handlePaste}
                                className="flex-1 gap-1"
                            >
                                <Upload className="h-3 w-3" />
                                Paste
                            </Button>
                        </div>
                        {importError && (
                            <p className="mt-1 text-xs text-destructive">Invalid preset string</p>
                        )}
                    </div>

                    {/* Manual Import */}
                    <div className="mb-3">
                        <div className="flex gap-1">
                            <input
                                type="text"
                                value={importValue}
                                onChange={(e) => {
                                    setImportValue(e.target.value);
                                    setImportError(false);
                                }}
                                placeholder="dark|#1e1e1e|#775DD0,..."
                                className="h-8 flex-1 rounded border bg-background px-2 text-xs font-mono"
                            />
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleImport}
                                disabled={!importValue}
                            >
                                Apply
                            </Button>
                        </div>
                    </div>

                    {/* Reset */}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onReset}
                        className="w-full gap-1 text-muted-foreground"
                    >
                        <RotateCcw className="h-3 w-3" />
                        Reset to Default
                    </Button>
                </div>,
                document.body
            )}
        </div>
    );
}
