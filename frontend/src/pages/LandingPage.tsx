import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Search,
    Loader2,
    MapPin,
    Navigation,
    AlertCircle,
    ChevronDown,
    ChevronUp,
    Check,
    Filter,
    LogIn,
    Building2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
    api,
    type PublicSearchRequest,
    type PublicSearchResponse,
} from "@/lib/api";
import { useAuth } from "@/lib";

// Available years for filter (2026-2022)
const AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022];
const DEFAULT_YEARS = [2025, 2024];

/**
 * LandingPage: Public landing page with simplified search
 * 
 * - No authentication required
 * - Search for DNO data by address, coordinates, or DNO name
 * - Login section below search to access full dashboard
 */
export default function LandingPage() {
    const { login, isAuthenticated, isLoading: authLoading } = useAuth();
    const navigate = useNavigate();

    // Search mode
    const [searchMode, setSearchMode] = useState<"address" | "coordinates" | "dno">("address");

    // Address inputs
    const [street, setStreet] = useState("");
    const [zipCode, setZipCode] = useState("");
    const [city, setCity] = useState("");

    // Coordinate inputs
    const [latitude, setLatitude] = useState("");
    const [longitude, setLongitude] = useState("");

    // DNO name input
    const [dnoName, setDnoName] = useState("");

    // Filter state
    const [filtersExpanded, setFiltersExpanded] = useState(false);
    const [selectedYears, setSelectedYears] = useState<number[]>(DEFAULT_YEARS);

    // State
    const [isSearching, setIsSearching] = useState(false);
    const [result, setResult] = useState<PublicSearchResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Toggle year selection
    const toggleYear = (year: number) => {
        setSelectedYears((prev) => {
            if (prev.includes(year)) {
                if (prev.length === 1) return prev;
                return prev.filter((y) => y !== year);
            }
            return [...prev, year].sort((a, b) => b - a);
        });
    };

    // Validation
    const isAddressValid =
        street.trim().length > 0 &&
        zipCode.trim().length >= 4 &&
        city.trim().length > 0;

    const isCoordinatesValid = () => {
        const lat = parseFloat(latitude.replace(",", "."));
        const lon = parseFloat(longitude.replace(",", "."));
        return (
            !isNaN(lat) &&
            !isNaN(lon) &&
            lat >= -90 &&
            lat <= 90 &&
            lon >= -180 &&
            lon <= 180
        );
    };

    const isDnoNameValid = dnoName.trim().length >= 2;

    const canSearch =
        (searchMode === "address" && isAddressValid) ||
        (searchMode === "coordinates" && isCoordinatesValid()) ||
        (searchMode === "dno" && isDnoNameValid);

    // Search handler
    const handleSearch = async () => {
        if (!canSearch) return;

        setError(null);
        setResult(null);
        setIsSearching(true);

        try {
            let request: PublicSearchRequest = {};

            if (searchMode === "address") {
                request.address = {
                    street: street.trim(),
                    zip_code: zipCode.trim(),
                    city: city.trim(),
                };
            } else if (searchMode === "coordinates") {
                request.coordinates = {
                    latitude: parseFloat(latitude.replace(",", ".")),
                    longitude: parseFloat(longitude.replace(",", ".")),
                };
            } else if (searchMode === "dno") {
                request.dno = {
                    dno_name: dnoName.trim(),
                };
            }

            if (selectedYears.length > 0) {
                request.years = selectedYears;
            }

            const response = await api.publicSearch.search(request);
            setResult(response);
        } catch (err: unknown) {
            if (err && typeof err === "object" && "response" in err) {
                const axiosErr = err as { response?: { status?: number; data?: { message?: string } } };
                if (axiosErr.response?.status === 429) {
                    setError("Rate limit exceeded. Please wait a moment and try again.");
                } else if (axiosErr.response?.status === 503) {
                    setError("Service temporarily unavailable. Please try again later.");
                } else {
                    setError(axiosErr.response?.data?.message || "Search failed. Please try again.");
                }
            } else {
                setError("Search failed. Please check your connection.");
            }
        } finally {
            setIsSearching(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && canSearch && !isSearching) {
            handleSearch();
        }
    };

    const handleLogin = () => {
        if (isAuthenticated) {
            navigate("/dashboard");
        } else {
            login();
        }
    };

    return (
        <div className="min-h-screen bg-background">
            {/* Hero Section */}
            <div className="relative overflow-hidden">
                {/* Background gradient */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-background to-background" />

                <div className="relative max-w-4xl mx-auto px-4 pt-16 pb-8">
                    {/* Branding */}
                    <div className="text-center mb-12">
                        <div className="flex items-center justify-center gap-3 mb-4">
                            <div className="p-2 rounded-xl bg-primary/10">
                                <svg className="h-12 w-12 text-emerald-400" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    {/* Connections */}
                                    <path d="M16 8v6" />
                                    <path d="M16 14L10 19" />
                                    <path d="M16 14L22 19" />
                                    {/* Nodes */}
                                    <circle cx="16" cy="14" r="2.5" fill="currentColor" stroke="none" />
                                    <circle cx="10" cy="19" r="1.5" fill="currentColor" stroke="none" />
                                    <circle cx="22" cy="19" r="1.5" fill="currentColor" stroke="none" />
                                    {/* Download tray/arrow */}
                                    <path d="M12 23h8" strokeOpacity="0.8" />
                                    <path d="M16 19v3" />
                                    <path d="M14 20l2 2 2-2" fill="none" />
                                    {/* Energy bolt */}
                                    <path d="M21 7l-1 3h2l-2 3" className="text-emerald-300" stroke="currentColor" strokeWidth="1.5" fill="none" />
                                </svg>
                            </div>
                        </div>
                        <h1 className="text-4xl font-bold text-gradient mb-4">
                            DNO Crawler
                        </h1>
                        <p className="text-lg text-muted-foreground max-w-lg mx-auto">
                            Search for German network operator data by address or coordinates.
                            Quick lookup without an account.
                        </p>
                    </div>

                    {/* Search Card */}
                    <Card>
                        <CardContent className="p-6 space-y-6">
                            {/* Mode Tabs */}
                            <div className="flex gap-2 border-b border-border pb-4">
                                <Button
                                    variant={searchMode === "address" ? "default" : "ghost"}
                                    size="sm"
                                    onClick={() => setSearchMode("address")}
                                    className="gap-2"
                                >
                                    <MapPin className="w-4 h-4" />
                                    Address
                                </Button>
                                <Button
                                    variant={searchMode === "coordinates" ? "default" : "ghost"}
                                    size="sm"
                                    onClick={() => setSearchMode("coordinates")}
                                    className="gap-2"
                                >
                                    <Navigation className="w-4 h-4" />
                                    Coordinates
                                </Button>
                                <Button
                                    variant={searchMode === "dno" ? "default" : "ghost"}
                                    size="sm"
                                    onClick={() => setSearchMode("dno")}
                                    className="gap-2"
                                >
                                    <Building2 className="w-4 h-4" />
                                    DNO Name
                                </Button>
                            </div>

                            {/* Address Input */}
                            {searchMode === "address" && (
                                <div className="space-y-4">
                                    <Input
                                        placeholder="Street + House Number (e.g. Musterstraße 123)"
                                        value={street}
                                        onChange={(e) => setStreet(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        disabled={isSearching}
                                    />
                                    <div className="grid grid-cols-2 gap-4">
                                        <Input
                                            placeholder="Zip Code (e.g. 50667)"
                                            value={zipCode}
                                            onChange={(e) => setZipCode(e.target.value)}
                                            onKeyDown={handleKeyDown}
                                            disabled={isSearching}
                                            maxLength={5}
                                        />
                                        <Input
                                            placeholder="City (e.g. Köln)"
                                            value={city}
                                            onChange={(e) => setCity(e.target.value)}
                                            onKeyDown={handleKeyDown}
                                            disabled={isSearching}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* Coordinates Input */}
                            {searchMode === "coordinates" && (
                                <div className="grid grid-cols-2 gap-4">
                                    <Input
                                        placeholder="Latitude (e.g. 50.9413)"
                                        value={latitude}
                                        onChange={(e) => setLatitude(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        disabled={isSearching}
                                    />
                                    <Input
                                        placeholder="Longitude (e.g. 6.9578)"
                                        value={longitude}
                                        onChange={(e) => setLongitude(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        disabled={isSearching}
                                    />
                                </div>
                            )}

                            {/* DNO Name Input */}
                            {searchMode === "dno" && (
                                <div className="space-y-2">
                                    <Input
                                        placeholder="DNO Name (e.g. Netze BW, RheinEnergie, Westnetz)"
                                        value={dnoName}
                                        onChange={(e) => setDnoName(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        disabled={isSearching}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Fuzzy search - partial names work (e.g. "Netze" will match "Netze BW GmbH")
                                    </p>
                                </div>
                            )}

                            {/* Collapsible Year Filter */}
                            <div className="border rounded-lg overflow-hidden">
                                <button
                                    type="button"
                                    onClick={() => setFiltersExpanded(!filtersExpanded)}
                                    className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                                >
                                    <div className="flex items-center gap-2 text-sm font-medium">
                                        <Filter className="w-4 h-4" />
                                        <span>Year Filter</span>
                                        <div className="flex gap-1 ml-2">
                                            {selectedYears.map((year) => (
                                                <Badge key={year} variant="secondary" className="text-xs">
                                                    {year}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                    {filtersExpanded ? (
                                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                                    ) : (
                                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                    )}
                                </button>

                                {filtersExpanded && (
                                    <div className="p-4 border-t bg-background">
                                        <label className="text-sm font-medium text-muted-foreground mb-3 block">
                                            Select Years (at least one required)
                                        </label>
                                        <div className="flex flex-wrap gap-2">
                                            {AVAILABLE_YEARS.map((year) => {
                                                const isSelected = selectedYears.includes(year);
                                                return (
                                                    <button
                                                        key={year}
                                                        type="button"
                                                        onClick={() => toggleYear(year)}
                                                        className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm font-medium transition-colors ${isSelected
                                                            ? "bg-primary text-primary-foreground border-primary"
                                                            : "bg-background border-input hover:bg-muted"
                                                            }`}
                                                    >
                                                        <div className={`w-4 h-4 rounded border flex items-center justify-center ${isSelected
                                                            ? "bg-primary-foreground/20 border-primary-foreground/50"
                                                            : "border-current opacity-50"
                                                            }`}>
                                                            {isSelected && (
                                                                <Check className="w-3 h-3" />
                                                            )}
                                                        </div>
                                                        {year}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Search Button */}
                            <Button
                                onClick={handleSearch}
                                disabled={!canSearch || isSearching}
                                className="w-full gap-2"
                                size="lg"
                            >
                                {isSearching ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Search className="w-4 h-4" />
                                )}
                                Search
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Error */}
                    {error && (
                        <Alert variant="destructive" className="mt-6">
                            <AlertCircle className="h-4 w-4" />
                            <AlertTitle>Error</AlertTitle>
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {/* Result */}
                    {result && (
                        <Card className="mt-6">
                            {result.found && result.dno ? (
                                <>
                                    <CardHeader>
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <CardTitle className="text-xl">{result.dno.name}</CardTitle>
                                                {result.dno.official_name && (
                                                    <CardDescription>{result.dno.official_name}</CardDescription>
                                                )}
                                            </div>
                                            <Badge variant={result.has_data ? "default" : "secondary"}>
                                                {result.has_data ? "Data Available" : "Skeleton"}
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        {/* Location Info */}
                                        {result.location && (
                                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                <MapPin className="w-4 h-4" />
                                                {result.location.street}, {result.location.zip_code} {result.location.city}
                                            </div>
                                        )}

                                        {result.has_data ? (
                                            /* Data Preview */
                                            <div className="space-y-3">
                                                {result.netzentgelte && result.netzentgelte.length > 0 && (
                                                    <div className="p-3 rounded-lg bg-muted/50">
                                                        <div className="text-sm font-medium mb-2">
                                                            Netzentgelte ({result.netzentgelte.length} records)
                                                        </div>
                                                        <div className="text-xs text-muted-foreground">
                                                            Years: {[...new Set(result.netzentgelte.map((n) => n.year))].join(", ")}
                                                        </div>
                                                    </div>
                                                )}
                                                {result.hlzf && result.hlzf.length > 0 && (
                                                    <div className="p-3 rounded-lg bg-muted/50">
                                                        <div className="text-sm font-medium mb-2">
                                                            HLZF ({result.hlzf.length} records)
                                                        </div>
                                                        <div className="text-xs text-muted-foreground">
                                                            Years: {[...new Set(result.hlzf.map((h) => h.year))].join(", ")}
                                                        </div>
                                                    </div>
                                                )}
                                                <div className="text-sm text-muted-foreground text-center pt-2">
                                                    <LogIn className="w-4 h-4 inline mr-2" />
                                                    Login to view full data and manage imports
                                                </div>
                                            </div>
                                        ) : (
                                            /* Skeleton - No data yet */
                                            <Alert>
                                                <AlertCircle className="h-4 w-4" />
                                                <AlertTitle>No data yet</AlertTitle>
                                                <AlertDescription>
                                                    {result.message || "This DNO has been registered but no data has been crawled yet. Login to import data."}
                                                </AlertDescription>
                                            </Alert>
                                        )}
                                    </CardContent>
                                </>
                            ) : (
                                /* Not Found */
                                <CardContent className="p-6 text-center">
                                    <AlertCircle className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                                    <p className="text-lg font-medium">No DNO Found</p>
                                    <p className="text-muted-foreground mt-2">
                                        {result.message || "No distribution network operator found for this location."}
                                    </p>
                                </CardContent>
                            )}
                        </Card>
                    )}

                    {/* Login Section */}
                    <Card className="mt-8 border-dashed">
                        <CardContent className="p-6 text-center">
                            <LogIn className="w-10 h-10 mx-auto text-primary mb-4" />
                            <h2 className="text-xl font-semibold mb-2">
                                {isAuthenticated ? "Go to Dashboard" : "Login to Access More"}
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                {isAuthenticated
                                    ? "You're already logged in. Access the full dashboard to manage DNOs and import data."
                                    : "Sign in to view full data, manage DNOs, trigger data imports, and access the admin dashboard."
                                }
                            </p>
                            <Button
                                onClick={handleLogin}
                                size="lg"
                                className="gap-2"
                                disabled={authLoading}
                            >
                                {authLoading ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <LogIn className="w-4 h-4" />
                                )}
                                {isAuthenticated ? "Open Dashboard" : "Login with Zitadel"}
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
