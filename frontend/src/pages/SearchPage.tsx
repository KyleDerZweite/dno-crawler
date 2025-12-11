import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
    Search,
    Filter,
    Loader2,
    CheckCircle2,
    XCircle,
    Circle,
    Clock,
    ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { api, type SearchFilters, type SearchJobStatus, type SearchStep } from "@/lib/api";

// Current year for default filters
const CURRENT_YEAR = new Date().getFullYear();
const LAST_YEAR = CURRENT_YEAR - 1;

/**
 * SearchPage: Natural language search with Task Timeline UI
 * 
 * States:
 * 1. Input: Search bar centered, filters below
 * 2. Searching: Search bar moves up, timeline appears
 * 3. Results: Timeline complete, results displayed
 */
export default function SearchPage() {
    const navigate = useNavigate();

    // Input state
    const [prompt, setPrompt] = useState("");
    const [filters, setFilters] = useState<SearchFilters>({
        years: [LAST_YEAR, CURRENT_YEAR],
        types: ["netzentgelte", "hlzf"],
    });

    // Job state
    const [jobId, setJobId] = useState<string | null>(null);
    const [jobStatus, setJobStatus] = useState<SearchJobStatus | null>(null);
    const [isSearching, setIsSearching] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Toggle filter
    const toggleYear = (year: number) => {
        setFilters(prev => ({
            ...prev,
            years: prev.years.includes(year)
                ? prev.years.filter(y => y !== year)
                : [...prev.years, year].sort(),
        }));
    };

    const toggleType = (type: string) => {
        setFilters(prev => {
            const newTypes = prev.types.includes(type)
                ? prev.types.filter(t => t !== type)
                : [...prev.types, type];
            // Ensure at least one type is selected
            return { ...prev, types: newTypes.length > 0 ? newTypes : prev.types };
        });
    };

    // Start search
    const handleSearch = async () => {
        if (!prompt.trim()) return;

        setError(null);
        setIsSearching(true);

        try {
            const response = await api.search.create(prompt, filters);
            setJobId(response.job_id);
        } catch (err) {
            setError("Failed to start search. Please try again.");
            setIsSearching(false);
        }
    };

    // Poll for job status
    useEffect(() => {
        if (!jobId) return;

        const pollInterval = setInterval(async () => {
            try {
                const status = await api.search.getStatus(jobId);
                setJobStatus(status);

                if (status.status === "completed" || status.status === "failed") {
                    clearInterval(pollInterval);
                    setIsSearching(false);

                    if (status.status === "failed") {
                        setError(status.error || "Search failed");
                    }
                }
            } catch (err) {
                console.error("Failed to poll job status:", err);
            }
        }, 1500); // Poll every 1.5 seconds

        return () => clearInterval(pollInterval);
    }, [jobId]);

    // Handle key press
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !isSearching) {
            handleSearch();
        }
    };

    // Render step indicator
    const renderStepIndicator = (step: SearchStep) => {
        switch (step.status) {
            case "running":
                return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
            case "done":
                return <CheckCircle2 className="w-4 h-4 text-success" />;
            case "failed":
                return <XCircle className="w-4 h-4 text-destructive" />;
            default:
                return <Circle className="w-4 h-4 text-muted-foreground" />;
        }
    };

    const hasStartedSearching = jobId !== null;
    const isComplete = jobStatus?.status === "completed";
    const result = jobStatus?.result;

    return (
        <div className="space-y-8">
            {/* Header - matches Dashboard style */}
            <div>
                <h1 className="text-3xl font-bold text-foreground">Search</h1>
                <p className="text-muted-foreground mt-2">
                    Find DNO data using natural language
                </p>
            </div>

            {/* Search Container - Animates up when searching */}
            <div
                className={`transition-all duration-500 ease-out ${hasStartedSearching ? "translate-y-0" : "translate-y-12"
                    }`}
            >
                <Card className="p-6">
                    <CardContent className="p-0">
                        {/* Search Input */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                            <Input
                                placeholder="Enter an address, e.g. 'Musterstraße 5, 50667 Köln'"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                onKeyDown={handleKeyDown}
                                disabled={isSearching}
                                className="pl-10 h-12 text-lg"
                            />
                            <Button
                                onClick={handleSearch}
                                disabled={!prompt.trim() || isSearching}
                                className="absolute right-2 top-1/2 -translate-y-1/2"
                            >
                                {isSearching ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    "Search"
                                )}
                            </Button>
                        </div>

                        {/* Filters */}
                        <div className="mt-4 flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                                <Filter className="w-4 h-4 text-muted-foreground" />
                                <span className="text-sm text-muted-foreground">Years:</span>
                                <div className="flex gap-1">
                                    {[LAST_YEAR, CURRENT_YEAR].map(year => (
                                        <Toggle
                                            key={year}
                                            pressed={filters.years.includes(year)}
                                            onPressedChange={() => toggleYear(year)}
                                            disabled={isSearching}
                                            size="sm"
                                            variant="outline"
                                        >
                                            {year}
                                        </Toggle>
                                    ))}
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground">Data:</span>
                                <div className="flex gap-1">
                                    <Toggle
                                        pressed={filters.types.includes("netzentgelte")}
                                        onPressedChange={() => toggleType("netzentgelte")}
                                        disabled={isSearching}
                                        size="sm"
                                        variant="outline"
                                    >
                                        Netzentgelte
                                    </Toggle>
                                    <Toggle
                                        pressed={filters.types.includes("hlzf")}
                                        onPressedChange={() => toggleType("hlzf")}
                                        disabled={isSearching}
                                        size="sm"
                                        variant="outline"
                                    >
                                        HLZF
                                    </Toggle>
                                </div>
                            </div>

                            {filters.years.length === 0 && (
                                <span className="text-xs text-muted-foreground italic">
                                    ℹ️ Specify year in your query
                                </span>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Timeline */}
            {hasStartedSearching && (
                <Card className="p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <CardHeader className="p-0 pb-4">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Clock className="w-5 h-5" />
                            Search Progress
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {jobStatus?.steps_history.map((step, index) => (
                                <div key={step.step} className="flex gap-4">
                                    {/* Indicator column */}
                                    <div className="flex flex-col items-center">
                                        {renderStepIndicator(step)}
                                        {index < (jobStatus?.steps_history.length || 0) - 1 && (
                                            <div className="w-0.5 h-8 bg-muted mt-1" />
                                        )}
                                    </div>

                                    {/* Content column */}
                                    <div className="flex-1 pb-4">
                                        <p className="font-medium">{step.label}</p>
                                        <p className="text-sm text-muted-foreground">
                                            {step.detail}
                                        </p>
                                    </div>
                                </div>
                            ))}

                            {/* Show pending indicator while searching */}
                            {isSearching && jobStatus?.steps_history.length === 0 && (
                                <div className="flex gap-4">
                                    <Loader2 className="w-4 h-4 text-primary animate-spin" />
                                    <p className="text-muted-foreground">Starting search...</p>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Error Display */}
            {error && (
                <Card className="p-6 border-destructive">
                    <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-destructive">
                            <XCircle className="w-5 h-5" />
                            <p>{error}</p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Results */}
            {isComplete && result && (
                <Card className="p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <CardHeader className="p-0 pb-4">
                        <div className="flex items-center justify-between">
                            <CardTitle className="flex items-center gap-2">
                                <CheckCircle2 className="w-5 h-5 text-success" />
                                Found: {result.dno_name}
                            </CardTitle>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => navigate(`/dnos/${encodeURIComponent(result.dno_name.toLowerCase().replace(/\s+/g, "-"))}`)}
                            >
                                View DNO Page
                                <ChevronRight className="w-4 h-4 ml-1" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-6 md:grid-cols-2">
                            {/* Netzentgelte Results */}
                            {Object.keys(result.netzentgelte).length > 0 && (
                                <div>
                                    <h3 className="font-semibold mb-2">Netzentgelte</h3>
                                    {Object.entries(result.netzentgelte).map(([year, records]) => (
                                        <div key={year} className="mb-2">
                                            <Badge variant="outline">{year}</Badge>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                {Array.isArray(records) ? records.length : 0} records found
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* HLZF Results */}
                            {Object.keys(result.hlzf).length > 0 && (
                                <div>
                                    <h3 className="font-semibold mb-2">HLZF</h3>
                                    {Object.entries(result.hlzf).map(([year, records]) => (
                                        <div key={year} className="mb-2">
                                            <Badge variant="outline">{year}</Badge>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                {Array.isArray(records) ? records.length : 0} records found
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* No data found */}
                            {Object.keys(result.netzentgelte).length === 0 &&
                                Object.keys(result.hlzf).length === 0 && (
                                    <p className="text-muted-foreground col-span-2">
                                        DNO identified but no data extracted.
                                        Try visiting the DNO page for more options.
                                    </p>
                                )}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
