import { useState } from "react";
import { Link } from "react-router-dom";
import {
    Search,
    Loader2,
    MapPin,
    Navigation,
    AlertCircle,
    ArrowRight,
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

/**
 * SearchPage: Simplified search using decoupled public search API
 *
 * Flow:
 * 1. User enters address/coordinates/DNO name
 * 2. Submit → POST /api/v1/search/
 * 3. If has_data: Show data preview + link to DNO page
 * 4. If !has_data (skeleton): Show "Import Data" → navigate to DNO page
 */
export default function SearchPage() {

    // Search mode
    const [searchMode, setSearchMode] = useState<"address" | "coordinates">("address");

    // Address inputs
    const [street, setStreet] = useState("");
    const [zipCode, setZipCode] = useState("");
    const [city, setCity] = useState("");

    // Coordinate inputs
    const [latitude, setLatitude] = useState("");
    const [longitude, setLongitude] = useState("");

    // State
    const [isSearching, setIsSearching] = useState(false);
    const [result, setResult] = useState<PublicSearchResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

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

    const canSearch =
        (searchMode === "address" && isAddressValid) ||
        (searchMode === "coordinates" && isCoordinatesValid());

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
            } else {
                request.coordinates = {
                    latitude: parseFloat(latitude.replace(",", ".")),
                    longitude: parseFloat(longitude.replace(",", ".")),
                };
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

    return (
        <div className="space-y-8 max-w-3xl mx-auto">
            {/* Header */}
            <div className="text-center">
                <h1 className="text-3xl font-bold text-foreground">Search DNO Data</h1>
                <p className="text-muted-foreground mt-2">
                    Find network operator data by address or coordinates
                </p>
            </div>

            {/* Search Card */}
            <Card>
                <CardContent className="p-6 space-y-6">
                    {/* Mode Tabs */}
                    <div className="flex gap-2 border-b pb-4">
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
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            {/* Result */}
            {result && (
                <Card>
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
                                        <Button asChild className="w-full gap-2">
                                            <Link to={`/dnos/${result.dno.slug}`}>
                                                View Full Data
                                                <ArrowRight className="w-4 h-4" />
                                            </Link>
                                        </Button>
                                    </div>
                                ) : (
                                    /* Skeleton - Import CTA */
                                    <div className="space-y-4">
                                        <Alert>
                                            <AlertCircle className="h-4 w-4" />
                                            <AlertTitle>No data yet</AlertTitle>
                                            <AlertDescription>
                                                {result.message || "This DNO has been registered but no data has been crawled yet."}
                                            </AlertDescription>
                                        </Alert>
                                        <Button asChild className="w-full gap-2">
                                            <Link to={`/dnos/${result.dno.slug}`}>
                                                Import Data
                                                <ArrowRight className="w-4 h-4" />
                                            </Link>
                                        </Button>
                                    </div>
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
        </div>
    );
}
