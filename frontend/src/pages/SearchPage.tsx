import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
    Search,
    Filter,
    Loader2,
    Clock,
    CheckCircle2,
    XCircle,
    AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { api, type SearchFilters, type SearchJobListItem } from "@/lib/api";

// Current year for default filters
const CURRENT_YEAR = new Date().getFullYear();
const LAST_YEAR = CURRENT_YEAR - 1;

/**
 * SearchPage: Main search landing page
 * 
 * URL: /search
 * 
 * Shows:
 * - Active search input with filters
 * - History of past searches below
 * 
 * On submit → redirects to /search/:jobId
 */
export default function SearchPage() {
    const navigate = useNavigate();

    // Input state
    const [prompt, setPrompt] = useState("");
    const [filters, setFilters] = useState<SearchFilters>({
        years: [LAST_YEAR, CURRENT_YEAR],
        types: ["netzentgelte", "hlzf"],
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch search history
    const { data: history, isLoading: historyLoading } = useQuery({
        queryKey: ["search-history"],
        queryFn: () => api.search.getHistory(20),
    });

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
            return { ...prev, types: newTypes.length > 0 ? newTypes : prev.types };
        });
    };

    // Start search and redirect
    const handleSearch = async () => {
        if (!prompt.trim()) return;

        setError(null);
        setIsSubmitting(true);

        try {
            const response = await api.search.create(prompt, filters);
            // Redirect to job page
            navigate(`/search/${response.job_id}`);
        } catch (err) {
            setError("Failed to start search. Please try again.");
            setIsSubmitting(false);
        }
    };

    // Handle key press
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !isSubmitting) {
            handleSearch();
        }
    };

    // Get status icon for history item
    const getStatusIcon = (status: string) => {
        switch (status) {
            case "completed":
                return <CheckCircle2 className="w-4 h-4 text-green-500" />;
            case "failed":
                return <XCircle className="w-4 h-4 text-destructive" />;
            case "running":
                return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
            default:
                return <Clock className="w-4 h-4 text-muted-foreground" />;
        }
    };

    // Format date
    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return "Just now";
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-foreground">Search</h1>
                <p className="text-muted-foreground mt-2">
                    Find DNO data using natural language
                </p>
            </div>

            {/* Search Input Card */}
            <Card className="p-6">
                <CardContent className="p-0">
                    {/* Search Input */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                        <Input
                            placeholder="Enter an address or DNO name, e.g. 'Musterstraße 5, 50667 Köln'"
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            onKeyDown={handleKeyDown}
                            disabled={isSubmitting}
                            className="pl-10 pr-24 h-12 text-lg"
                        />
                        <Button
                            onClick={handleSearch}
                            disabled={!prompt.trim() || isSubmitting}
                            className="absolute right-2 top-1/2 -translate-y-1/2"
                        >
                            {isSubmitting ? (
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
                                        disabled={isSubmitting}
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
                                    disabled={isSubmitting}
                                    size="sm"
                                    variant="outline"
                                >
                                    Netzentgelte
                                </Toggle>
                                <Toggle
                                    pressed={filters.types.includes("hlzf")}
                                    onPressedChange={() => toggleType("hlzf")}
                                    disabled={isSubmitting}
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

                    {/* Error */}
                    {error && (
                        <div className="mt-4 flex items-center gap-2 text-destructive text-sm">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Search History - Narrower and centered */}
            <div className="max-w-2xl mx-auto mt-12">
                <h2 className="text-sm font-medium text-muted-foreground mb-4 text-center flex items-center justify-center gap-2">
                    <Clock className="w-4 h-4" />
                    Recent Searches
                </h2>

                {historyLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                ) : history && history.length > 0 ? (
                    <div className="space-y-2">
                        {history.map((item: SearchJobListItem) => (
                            <Card
                                key={item.job_id}
                                className="p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                                onClick={() => navigate(`/search/${item.job_id}`)}
                            >
                                <div className="flex items-center gap-3">
                                    {getStatusIcon(item.status)}
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{item.input_text}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {formatDate(item.created_at)}
                                        </p>
                                    </div>
                                    <Badge variant="outline" className="shrink-0 text-xs">
                                        {item.status}
                                    </Badge>
                                </div>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <Card className="p-6 text-center">
                        <p className="text-muted-foreground">
                            No search history yet. Start your first search above!
                        </p>
                    </Card>
                )}
            </div>
        </div>
    );
}
