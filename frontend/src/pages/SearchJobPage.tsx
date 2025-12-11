import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
    Search,
    Filter,
    Loader2,
    CheckCircle2,
    XCircle,
    Circle,
    Clock,
    ChevronRight,
    ChevronDown,
    ArrowLeft,
    Ban,
    Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { api, type SearchJobStatus, type SearchStep } from "@/lib/api";

// Current year for default filters display
const CURRENT_YEAR = new Date().getFullYear();
const LAST_YEAR = CURRENT_YEAR - 1;

// All possible steps in the search workflow (shown upfront)
const ALL_STEPS = [
    { key: "Analyzing Input", label: "Analyzing Input" },
    { key: "Checking Cache", label: "Checking Cache" },
    { key: "External Search", label: "External Search" },
    { key: "Analyzing Results", label: "Analyzing Results" },
    { key: "Finding PDF", label: "Finding PDF" },
    { key: "Downloading PDF", label: "Downloading PDF" },
    { key: "Validating PDF", label: "Validating PDF" },
    { key: "Extracting Data", label: "Extracting Data" },
];

/**
 * SearchJobPage: Display a specific search job's progress and results
 * 
 * URL: /search/:jobId
 * 
 * Shows:
 * - Full search UI with original query and filters (disabled)
 * - Timeline of job progress with all steps
 * - Results when complete
 */
export default function SearchJobPage() {
    const { jobId } = useParams<{ jobId: string }>();
    const navigate = useNavigate();

    const [jobStatus, setJobStatus] = useState<SearchJobStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isCancelling, setIsCancelling] = useState(false);
    const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

    // Cancel handler
    const handleCancel = async () => {
        if (!jobId || isCancelling) return;

        setIsCancelling(true);
        try {
            await api.search.cancel(jobId);
            // Refetch status to update UI
            const status = await api.search.getStatus(jobId);
            setJobStatus(status);
        } catch (err) {
            console.error("Failed to cancel:", err);
        } finally {
            setIsCancelling(false);
        }
    };

    // Initial load and polling
    useEffect(() => {
        if (!jobId) return;

        const fetchStatus = async () => {
            try {
                const status = await api.search.getStatus(jobId);
                setJobStatus(status);
                setIsLoading(false);

                // Stop polling if job is done
                if (status.status === "completed" || status.status === "failed" || status.status === "cancelled") {
                    return true;
                }
                return false;
            } catch (err) {
                setError("Failed to load search job");
                setIsLoading(false);
                return true;
            }
        };

        fetchStatus();

        const pollInterval = setInterval(async () => {
            const shouldStop = await fetchStatus();
            if (shouldStop) {
                clearInterval(pollInterval);
            }
        }, 1500);

        return () => clearInterval(pollInterval);
    }, [jobId]);

    const isRunning = jobStatus?.status === "running" || jobStatus?.status === "pending";
    const isComplete = jobStatus?.status === "completed";
    const isFailed = jobStatus?.status === "failed";
    const isCancelled = jobStatus?.status === "cancelled";
    const result = jobStatus?.result;

    // Get filters from job or use defaults
    const years = jobStatus?.filters?.years || [LAST_YEAR, CURRENT_YEAR];
    const types = jobStatus?.filters?.types || ["netzentgelte", "hlzf"];

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error || !jobStatus) {
        return (
            <div className="space-y-8">
                <div>
                    <h1 className="text-3xl font-bold text-foreground">Search</h1>
                    <p className="text-muted-foreground mt-2">Job not found</p>
                </div>
                <Card className="p-6 border-destructive">
                    <div className="flex items-center gap-2 text-destructive">
                        <XCircle className="w-5 h-5" />
                        <p>{error || "This search job doesn't exist or you don't have access."}</p>
                    </div>
                    <Button
                        variant="outline"
                        className="mt-4"
                        onClick={() => navigate("/search")}
                    >
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back to Search
                    </Button>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Header with back button and cancel */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => navigate("/search")}
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-bold text-foreground">Search</h1>
                        <p className="text-muted-foreground mt-1">
                            {isRunning ? "Searching..." :
                                isComplete ? "Search complete" :
                                    isCancelled ? "Search cancelled" :
                                        "Search failed"}
                        </p>
                    </div>
                </div>

                {/* Cancel button - only show when running */}
                {isRunning && (
                    <Button
                        variant="outline"
                        onClick={handleCancel}
                        disabled={isCancelling}
                        className="text-destructive border-destructive/50 hover:bg-destructive/10"
                    >
                        {isCancelling ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <Ban className="w-4 h-4 mr-2" />
                        )}
                        Cancel
                    </Button>
                )}
            </div>

            {/* Search Input Card - Disabled, shows original query */}
            <Card className="p-6">
                <CardContent className="p-0">
                    {/* Search Input - Disabled */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                        <Input
                            value={jobStatus.input_text || ""}
                            disabled
                            className="pl-10 pr-24 h-12 text-lg bg-muted/30"
                        />
                        <Button
                            disabled
                            className="absolute right-2 top-1/2 -translate-y-1/2 opacity-50"
                        >
                            {isRunning ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : isComplete ? (
                                <CheckCircle2 className="w-4 h-4" />
                            ) : (
                                "Search"
                            )}
                        </Button>
                    </div>

                    {/* Filters - Disabled */}
                    <div className="mt-4 flex flex-wrap items-center gap-4 opacity-60">
                        <div className="flex items-center gap-2">
                            <Filter className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm text-muted-foreground">Years:</span>
                            <div className="flex gap-1">
                                {[LAST_YEAR, CURRENT_YEAR].map(year => (
                                    <Toggle
                                        key={year}
                                        pressed={years.includes(year)}
                                        disabled
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
                                    pressed={types.includes("netzentgelte")}
                                    disabled
                                    size="sm"
                                    variant="outline"
                                >
                                    Netzentgelte
                                </Toggle>
                                <Toggle
                                    pressed={types.includes("hlzf")}
                                    disabled
                                    size="sm"
                                    variant="outline"
                                >
                                    HLZF
                                </Toggle>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Progress Timeline */}
            <Card className="p-6">
                <CardHeader className="p-0 pb-4">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Clock className="w-5 h-5" />
                        Progress
                        {isRunning && (
                            <Badge variant="outline" className="ml-2 text-xs">
                                In Progress
                            </Badge>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="space-y-1">
                        {/* Build merged steps: ALL_STEPS with backend status */}
                        {(() => {
                            // Create a map of backend steps by label for quick lookup
                            const stepsMap = new Map<string, SearchStep>();
                            for (const step of jobStatus.steps_history) {
                                stepsMap.set(step.label, step);
                            }

                            return ALL_STEPS.map((stepDef, index) => {
                                const backendStep = stepsMap.get(stepDef.key);
                                const status = backendStep?.status || "pending";
                                const detail = backendStep?.detail || "";
                                const isLast = index === ALL_STEPS.length - 1;
                                const isActive = status === "running";
                                const isExpanded = expandedSteps.has(stepDef.key);
                                const hasDetail = status !== "pending" && detail;

                                // Toggle expansion
                                const toggleExpand = () => {
                                    if (!hasDetail && status === "pending") return;
                                    setExpandedSteps(prev => {
                                        const next = new Set(prev);
                                        if (next.has(stepDef.key)) {
                                            next.delete(stepDef.key);
                                        } else {
                                            next.add(stepDef.key);
                                        }
                                        return next;
                                    });
                                };

                                // Determine indicator icon
                                const renderIndicator = () => {
                                    switch (status) {
                                        case "running":
                                            return (
                                                <div className="w-5 h-5 flex-shrink-0 flex items-center justify-center rounded-full bg-primary/20 animate-pulse">
                                                    <Play className="w-3 h-3 text-primary fill-primary" />
                                                </div>
                                            );
                                        case "done":
                                            return <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />;
                                        case "failed":
                                            return <XCircle className="w-5 h-5 text-destructive flex-shrink-0" />;
                                        default:
                                            return <Circle className="w-5 h-5 text-muted-foreground/30 flex-shrink-0" />;
                                    }
                                };

                                // Get detailed description for expanded view
                                const getExpandedDetail = () => {
                                    if (stepDef.key === "External Search") {
                                        const inputText = jobStatus.input_text || "";
                                        return (
                                            <div className="mt-2 p-3 bg-muted/30 rounded-md text-sm">
                                                <div className="font-medium text-muted-foreground mb-1">Search Query:</div>
                                                <div className="text-foreground">"{inputText}"</div>
                                                {detail && (
                                                    <>
                                                        <div className="font-medium text-muted-foreground mt-2 mb-1">Result:</div>
                                                        <div className="text-foreground">{detail}</div>
                                                    </>
                                                )}
                                            </div>
                                        );
                                    }
                                    if (stepDef.key === "Analyzing Input") {
                                        return (
                                            <div className="mt-2 p-3 bg-muted/30 rounded-md text-sm">
                                                <div className="font-medium text-muted-foreground mb-1">Parsed Address:</div>
                                                <div className="text-foreground font-mono">{detail}</div>
                                            </div>
                                        );
                                    }
                                    return detail ? (
                                        <div className="mt-2 p-3 bg-muted/30 rounded-md text-sm text-foreground">
                                            {detail}
                                        </div>
                                    ) : null;
                                };

                                // Brief summary for collapsed state
                                const getBriefStatus = () => {
                                    if (status === "pending") return null;
                                    if (status === "running") return "In progress...";
                                    if (status === "failed") return "Failed";
                                    // For done: show brief excerpt
                                    if (detail.length > 40) {
                                        return detail.slice(0, 37) + "...";
                                    }
                                    return detail || "Complete";
                                };

                                return (
                                    <div key={stepDef.key}>
                                        <div
                                            onClick={status !== "pending" ? toggleExpand : undefined}
                                            className={`flex gap-4 items-start py-3 px-2 rounded-lg transition-colors ${isActive ? "bg-primary/5 border border-primary/20" :
                                                    status === "pending" ? "opacity-50" :
                                                        "hover:bg-muted/30 cursor-pointer"
                                                }`}
                                        >
                                            {/* Indicator + connector line */}
                                            <div className="flex flex-col items-center">
                                                {renderIndicator()}
                                                {!isLast && (
                                                    <div className={`w-0.5 h-6 mt-1 ${status === "done" ? "bg-green-500/30" :
                                                            status === "running" ? "bg-primary/30" :
                                                                "bg-muted/30"
                                                        }`} />
                                                )}
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <p className={`font-medium ${status === "failed" ? "text-destructive" :
                                                            status === "pending" ? "text-muted-foreground" : ""
                                                        }`}>
                                                        {stepDef.label}
                                                    </p>
                                                    {status !== "pending" && (
                                                        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-180" : ""
                                                            }`} />
                                                    )}
                                                </div>
                                                {!isExpanded && getBriefStatus() && (
                                                    <p className="text-sm text-muted-foreground truncate">
                                                        {getBriefStatus()}
                                                    </p>
                                                )}
                                            </div>

                                            {/* Status badge */}
                                            <Badge
                                                variant="outline"
                                                className={`text-xs shrink-0 ${status === "done" ? "border-green-500/50 text-green-500" :
                                                        status === "running" ? "border-primary/50 text-primary" :
                                                            status === "failed" ? "border-destructive/50 text-destructive" :
                                                                "border-muted-foreground/30 text-muted-foreground/50"
                                                    }`}
                                            >
                                                {status}
                                            </Badge>
                                        </div>

                                        {/* Expanded details */}
                                        {isExpanded && status !== "pending" && (
                                            <div className="ml-9 mb-2">
                                                {getExpandedDetail()}
                                            </div>
                                        )}
                                    </div>
                                );
                            });
                        })()}
                    </div>
                </CardContent>
            </Card>

            {/* Error Display */}
            {isFailed && (
                <Card className="p-6 border-destructive">
                    <div className="flex items-center gap-2 text-destructive">
                        <XCircle className="w-5 h-5" />
                        <p className="font-medium">Search Failed</p>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                        {jobStatus.error || "An unknown error occurred"}
                    </p>
                    <Button
                        variant="outline"
                        className="mt-4"
                        onClick={() => navigate("/search")}
                    >
                        Try Again
                    </Button>
                </Card>
            )}

            {/* Cancelled Display */}
            {isCancelled && (
                <Card className="p-6 border-muted">
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Ban className="w-5 h-5" />
                        <p className="font-medium">Search Cancelled</p>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                        This search was cancelled by the user.
                    </p>
                    <Button
                        variant="outline"
                        className="mt-4"
                        onClick={() => navigate("/search")}
                    >
                        Start New Search
                    </Button>
                </Card>
            )}

            {/* Results */}
            {isComplete && result && (
                <Card className="p-6">
                    <CardHeader className="p-0 pb-4">
                        <div className="flex items-center justify-between">
                            <CardTitle className="flex items-center gap-2">
                                <CheckCircle2 className="w-5 h-5 text-green-500" />
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
                    <CardContent className="p-0">
                        <div className="grid gap-6 md:grid-cols-2">
                            {/* Netzentgelte */}
                            {Object.keys(result.netzentgelte).length > 0 && (
                                <div className="p-4 rounded-lg bg-muted/30">
                                    <h3 className="font-semibold mb-3">Netzentgelte</h3>
                                    {Object.entries(result.netzentgelte).map(([year, records]) => (
                                        <div key={year} className="flex items-center justify-between py-1">
                                            <Badge variant="outline">{year}</Badge>
                                            <span className="text-sm text-muted-foreground">
                                                {Array.isArray(records) ? records.length : 0} records
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* HLZF */}
                            {Object.keys(result.hlzf).length > 0 && (
                                <div className="p-4 rounded-lg bg-muted/30">
                                    <h3 className="font-semibold mb-3">HLZF</h3>
                                    {Object.entries(result.hlzf).map(([year, records]) => (
                                        <div key={year} className="flex items-center justify-between py-1">
                                            <Badge variant="outline">{year}</Badge>
                                            <span className="text-sm text-muted-foreground">
                                                {Array.isArray(records) ? records.length : 0} records
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* No data */}
                            {Object.keys(result.netzentgelte).length === 0 &&
                                Object.keys(result.hlzf).length === 0 && (
                                    <div className="col-span-2 p-4 rounded-lg bg-muted/30 text-center">
                                        <p className="text-muted-foreground">
                                            DNO identified but no data extracted. Visit the DNO page for more options.
                                        </p>
                                    </div>
                                )}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
