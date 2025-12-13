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
    MapPin,
    Building2,
    Navigation,
    ChevronDown,
    Plus,
    Trash2,
    Play,
    AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { api, type SearchFilters, type SearchJobListItem } from "@/lib/api";

// Current year for default filters
const CURRENT_YEAR = new Date().getFullYear();
const LAST_YEAR = CURRENT_YEAR - 1;

// Queue item types
interface QueueItem {
    id: string;
    type: "address" | "dno" | "coordinates";
    // Address type
    street?: string;
    plzCity?: string;
    // DNO type
    dnoName?: string;
    // Coordinates type
    longitude?: number;
    latitude?: number;
    // Display label
    label: string;
}

/**
 * Generate a unique ID for queue items
 */
function generateId(): string {
    return crypto.randomUUID();
}

/**
 * SearchPage: Main search landing page with structured inputs
 * 
 * URL: /search
 * 
 * Features:
 * - Address input (Street + PLZ/City)
 * - DNO name direct input
 * - Advanced: Coordinates input
 * - Local queue for batch processing
 * - History of past searches
 */
export default function SearchPage() {
    const navigate = useNavigate();

    // Input state for address
    const [street, setStreet] = useState("");
    const [plzCity, setPlzCity] = useState("");

    // Input state for DNO
    const [dnoName, setDnoName] = useState("");

    // Input state for coordinates (advanced)
    const [longitude, setLongitude] = useState("");
    const [latitude, setLatitude] = useState("");
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Queue state
    const [queue, setQueue] = useState<QueueItem[]>([]);

    // Filters
    const [filters, setFilters] = useState<SearchFilters>({
        years: [LAST_YEAR, CURRENT_YEAR],
        types: ["netzentgelte", "hlzf"],
    });

    // Submission state
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch search history (auto-refresh every 5s while running jobs)
    const { data: history, isLoading: historyLoading } = useQuery({
        queryKey: ["search-history"],
        queryFn: () => api.search.getHistory(20),
        refetchInterval: 5000,  // Refresh every 5 seconds
        refetchOnWindowFocus: true,  // Refresh when tab becomes active
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

    // Validation helpers
    const isAddressValid = street.trim().length > 0 && plzCity.trim().length > 0;
    const isDnoValid = dnoName.trim().length > 0;
    const isCoordinatesValid = () => {
        const lon = parseFloat(longitude.replace(",", "."));
        const lat = parseFloat(latitude.replace(",", "."));
        return !isNaN(lon) && !isNaN(lat) &&
            lon >= -180 && lon <= 180 &&
            lat >= -90 && lat <= 90;
    };

    const canAddAddress = isAddressValid;
    const canAddDno = isDnoValid;
    const canAddCoordinates = isCoordinatesValid();

    // Add to queue handlers
    const addAddressToQueue = () => {
        if (!canAddAddress) return;

        const item: QueueItem = {
            id: generateId(),
            type: "address",
            street: street.trim(),
            plzCity: plzCity.trim(),
            label: `${street.trim()}, ${plzCity.trim()}`,
        };
        setQueue(prev => [...prev, item]);
        setStreet("");
        setPlzCity("");
    };

    const addDnoToQueue = () => {
        if (!canAddDno) return;

        const item: QueueItem = {
            id: generateId(),
            type: "dno",
            dnoName: dnoName.trim(),
            label: dnoName.trim(),
        };
        setQueue(prev => [...prev, item]);
        setDnoName("");
    };

    const addCoordinatesToQueue = () => {
        if (!canAddCoordinates) return;

        const lon = parseFloat(longitude.replace(",", "."));
        const lat = parseFloat(latitude.replace(",", "."));

        const item: QueueItem = {
            id: generateId(),
            type: "coordinates",
            longitude: lon,
            latitude: lat,
            label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
        };
        setQueue(prev => [...prev, item]);
        setLongitude("");
        setLatitude("");
    };

    const removeFromQueue = (id: string) => {
        setQueue(prev => prev.filter(item => item.id !== id));
    };

    // Start batch search
    const handleStartBatch = async () => {
        if (queue.length === 0) return;

        setError(null);
        setIsSubmitting(true);

        try {
            // Convert queue items to API payload format
            const payloads = queue.map(item => {
                if (item.type === "address") {
                    return {
                        type: "address" as const,
                        address: { street: item.street!, plz_city: item.plzCity! },
                    };
                } else if (item.type === "dno") {
                    return {
                        type: "dno" as const,
                        dno: { dno_name: item.dnoName! },
                    };
                } else {
                    return {
                        type: "coordinates" as const,
                        coordinates: { longitude: item.longitude!, latitude: item.latitude! },
                    };
                }
            });

            const response = await api.search.createBatch(payloads, filters);

            // Navigate to batch view
            if (response.batch_id) {
                navigate(`/search/batch/${response.batch_id}`);
            }
        } catch (err) {
            setError("Failed to start batch search. Please try again.");
            setIsSubmitting(false);
        }
    };

    // Handle key press for Enter submission
    const handleAddressKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && canAddAddress && !isSubmitting) {
            addAddressToQueue();
        }
    };

    const handleDnoKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && canAddDno && !isSubmitting) {
            addDnoToQueue();
        }
    };

    const handleCoordsKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && canAddCoordinates && !isSubmitting) {
            addCoordinatesToQueue();
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

    // Get icon for queue item type
    const getQueueItemIcon = (type: QueueItem["type"]) => {
        switch (type) {
            case "address":
                return <MapPin className="w-4 h-4" />;
            case "dno":
                return <Building2 className="w-4 h-4" />;
            case "coordinates":
                return <Navigation className="w-4 h-4" />;
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
                    Find DNO data by address, name, or coordinates
                </p>
            </div>

            {/* Main Input Card */}
            <Card className="p-6">
                <CardContent className="p-0 space-y-6">

                    {/* Address Input Section */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                            <MapPin className="w-4 h-4 text-primary" />
                            Address
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <Input
                                placeholder="Street + Housenumber"
                                value={street}
                                onChange={(e) => setStreet(e.target.value)}
                                onKeyDown={handleAddressKeyDown}
                                disabled={isSubmitting}
                            />
                            <div className="flex gap-2">
                                <Input
                                    placeholder="PLZ + City (e.g. 50859 Köln)"
                                    value={plzCity}
                                    onChange={(e) => setPlzCity(e.target.value)}
                                    onKeyDown={handleAddressKeyDown}
                                    disabled={isSubmitting}
                                    className="flex-1"
                                />
                                <Button
                                    variant="secondary"
                                    size="icon"
                                    onClick={addAddressToQueue}
                                    disabled={!canAddAddress || isSubmitting}
                                    title="Add address to queue"
                                >
                                    <Plus className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                    </div>

                    {/* Divider */}
                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-card px-2 text-muted-foreground">or</span>
                        </div>
                    </div>

                    {/* DNO Input Section */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                            <Building2 className="w-4 h-4 text-primary" />
                            DNO Name (if known)
                        </div>
                        <div className="flex gap-2">
                            <Input
                                placeholder="e.g. RheinNetz, Westnetz, E.DIS"
                                value={dnoName}
                                onChange={(e) => setDnoName(e.target.value)}
                                onKeyDown={handleDnoKeyDown}
                                disabled={isSubmitting}
                                className="flex-1"
                            />
                            <Button
                                variant="secondary"
                                size="icon"
                                onClick={addDnoToQueue}
                                disabled={!canAddDno || isSubmitting}
                                title="Add DNO to queue"
                            >
                                <Plus className="w-4 h-4" />
                            </Button>
                        </div>
                    </div>

                    {/* Advanced Search (Collapsible) */}
                    <div className="border-t pt-4">
                        <button
                            type="button"
                            onClick={() => setShowAdvanced(!showAdvanced)}
                            className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                        >
                            <ChevronDown className={`w-4 h-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`} />
                            Advanced Search
                        </button>

                        {showAdvanced && (
                            <div className="mt-4 space-y-3 pl-6 border-l-2 border-muted">
                                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                                    <Navigation className="w-4 h-4 text-primary" />
                                    Coordinates
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <Input
                                        placeholder="Longitude (e.g. 6.9578)"
                                        value={longitude}
                                        onChange={(e) => setLongitude(e.target.value)}
                                        onKeyDown={handleCoordsKeyDown}
                                        disabled={isSubmitting}
                                    />
                                    <div className="flex gap-2">
                                        <Input
                                            placeholder="Latitude (e.g. 50.9413)"
                                            value={latitude}
                                            onChange={(e) => setLatitude(e.target.value)}
                                            onKeyDown={handleCoordsKeyDown}
                                            disabled={isSubmitting}
                                            className="flex-1"
                                        />
                                        <Button
                                            variant="secondary"
                                            size="icon"
                                            onClick={addCoordinatesToQueue}
                                            disabled={!canAddCoordinates || isSubmitting}
                                            title="Add coordinates to queue"
                                        >
                                            <Plus className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    Use decimal format with dot separator (e.g., 6.9578, 50.9413)
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Filters */}
                    <div className="border-t pt-4">
                        <div className="flex flex-wrap items-center gap-4">
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
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Queue Card */}
            {queue.length > 0 && (
                <Card className="p-6 border-primary/30">
                    <CardHeader className="p-0 pb-4">
                        <CardTitle className="text-lg flex items-center justify-between">
                            <span className="flex items-center gap-2">
                                <Search className="w-5 h-5" />
                                Search Queue
                                <Badge variant="secondary">{queue.length}</Badge>
                            </span>
                            <Button
                                onClick={handleStartBatch}
                                disabled={isSubmitting}
                                className="gap-2"
                            >
                                {isSubmitting ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Play className="w-4 h-4" />
                                )}
                                Start Batch ({queue.length})
                            </Button>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="space-y-2">
                            {queue.map((item) => (
                                <div
                                    key={item.id}
                                    className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 group"
                                >
                                    <div className="p-2 rounded-md bg-primary/10 text-primary">
                                        {getQueueItemIcon(item.type)}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{item.label}</p>
                                        <p className="text-xs text-muted-foreground capitalize">{item.type}</p>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => removeFromQueue(item.id)}
                                        disabled={isSubmitting}
                                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Error */}
            {error && (
                <Card className="p-4 border-destructive">
                    <div className="flex items-center gap-2 text-destructive text-sm">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                </Card>
            )}

            {/* Search History */}
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
                                onClick={() => {
                                    // Navigate to batch view if it's a batch, otherwise job view
                                    if (item.batch_id) {
                                        navigate(`/search/batch/${item.batch_id}`);
                                    } else {
                                        navigate(`/search/${item.job_id}`);
                                    }
                                }}
                            >
                                <div className="flex items-center gap-3">
                                    {getStatusIcon(item.status)}
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{item.input_text}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {formatDate(item.created_at)}
                                        </p>
                                    </div>
                                    {item.batch_id && item.batch_total ? (
                                        // Show batch progress
                                        <Badge variant="outline" className="shrink-0 text-xs">
                                            {item.batch_completed ?? 0}/{item.batch_total}
                                        </Badge>
                                    ) : (
                                        <Badge variant="outline" className="shrink-0 text-xs">
                                            {item.status}
                                        </Badge>
                                    )}
                                </div>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <Card className="p-6 text-center">
                        <p className="text-muted-foreground">
                            No search history yet. Add items to your queue and start your first search!
                        </p>
                    </Card>
                )}
            </div>
        </div>
    );
}
