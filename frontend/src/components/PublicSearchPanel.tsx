import { useState } from "react";
import { Link } from "react-router-dom";
import {
    Search,
    Loader2,
    MapPin,
    Navigation,
    AlertCircle,
    ArrowRight,
    ChevronDown,
    ChevronUp,
    Check,
    Filter,
    Building2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { api } from "@/lib/api";
import { DataPreviewTables } from "@/components/DataPreviewTables";
import type { PublicSearchRequest, PublicSearchResponse } from "@/types";

const AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022];
const DEFAULT_YEARS = [2025, 2024];
const COORD_PATTERN = /^-?\d{1,3}([.,]\d{1,10})?$/;

interface PublicSearchPanelProps {
    showImportLinkForSkeleton?: boolean;
    errorClassName?: string;
    resultClassName?: string;
}

export function PublicSearchPanel({
    showImportLinkForSkeleton = false,
    errorClassName,
    resultClassName,
}: PublicSearchPanelProps) {
    const [searchMode, setSearchMode] = useState<"address" | "coordinates" | "dno">("address");

    const [street, setStreet] = useState("");
    const [zipCode, setZipCode] = useState("");
    const [city, setCity] = useState("");

    const [latitude, setLatitude] = useState("");
    const [longitude, setLongitude] = useState("");

    const [dnoName, setDnoName] = useState("");

    const [filtersExpanded, setFiltersExpanded] = useState(false);
    const [selectedYears, setSelectedYears] = useState<number[]>(DEFAULT_YEARS);

    const [isSearching, setIsSearching] = useState(false);
    const [result, setResult] = useState<PublicSearchResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const toggleYear = (year: number) => {
        setSelectedYears((prev) => {
            if (prev.includes(year)) {
                if (prev.length === 1) return prev;
                return prev.filter((y) => y !== year);
            }
            return [...prev, year].sort((a, b) => b - a);
        });
    };

    const isAddressValid =
        street.trim().length > 0 &&
        zipCode.trim().length >= 4 &&
        city.trim().length > 0;

    const isCoordinatesValid = () => {
        const latStr = latitude.trim().replace(",", ".");
        const lonStr = longitude.trim().replace(",", ".");

        if (!latStr || !lonStr) return false;

        const lat = parseFloat(latStr);
        const lon = parseFloat(lonStr);

        if (isNaN(lat) || isNaN(lon)) return false;
        if (lat < -90 || lat > 90) return false;
        if (lon < -180 || lon > 180) return false;

        return COORD_PATTERN.test(latitude.trim()) && COORD_PATTERN.test(longitude.trim());
    };

    const getCoordinateError = (): string | null => {
        const latStr = latitude.trim().replace(",", ".");
        const lonStr = longitude.trim().replace(",", ".");

        if (!latStr && !lonStr) return null;

        if (latStr && !COORD_PATTERN.test(latitude.trim())) {
            return "Latitude must be a number like 50.9413 or 50,9413";
        }
        if (lonStr && !COORD_PATTERN.test(longitude.trim())) {
            return "Longitude must be a number like 6.9578 or 6,9578";
        }

        const lat = parseFloat(latStr);
        const lon = parseFloat(lonStr);

        if (!isNaN(lat) && (lat < -90 || lat > 90)) {
            return "Latitude must be between -90 and 90";
        }
        if (!isNaN(lon) && (lon < -180 || lon > 180)) {
            return "Longitude must be between -180 and 180";
        }

        return null;
    };

    const isDnoNameValid = dnoName.trim().length >= 2;

    const canSearch =
        (searchMode === "address" && isAddressValid) ||
        (searchMode === "coordinates" && isCoordinatesValid()) ||
        (searchMode === "dno" && isDnoNameValid);

    const handleSearch = async () => {
        if (!canSearch) return;

        setError(null);
        setResult(null);
        setIsSearching(true);

        try {
            const request: PublicSearchRequest = {};

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
                request.dno = { dno_name: dnoName.trim() };
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

    return (
        <>
            <Card>
                <CardContent className="p-6 space-y-6">
                    <div className="flex gap-2 border-b pb-4">
                        <Button
                            variant={searchMode === "address" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => { setSearchMode("address"); }}
                            className="gap-2"
                        >
                            <MapPin className="w-4 h-4" />
                            Address
                        </Button>
                        <Button
                            variant={searchMode === "coordinates" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => { setSearchMode("coordinates"); }}
                            className="gap-2"
                        >
                            <Navigation className="w-4 h-4" />
                            Coordinates
                        </Button>
                        <Button
                            variant={searchMode === "dno" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => { setSearchMode("dno"); }}
                            className="gap-2"
                        >
                            <Building2 className="w-4 h-4" />
                            DNO Name
                        </Button>
                    </div>

                    {searchMode === "address" && (
                        <div className="space-y-4">
                            <Input
                                placeholder="Street + House Number (e.g. Musterstraße 123)"
                                value={street}
                                onChange={(e) => { setStreet(e.target.value); }}
                                onKeyDown={handleKeyDown}
                                disabled={isSearching}
                            />
                            <div className="grid grid-cols-2 gap-4">
                                <Input
                                    placeholder="Zip Code (e.g. 50667)"
                                    value={zipCode}
                                    onChange={(e) => { setZipCode(e.target.value); }}
                                    onKeyDown={handleKeyDown}
                                    disabled={isSearching}
                                    maxLength={5}
                                />
                                <Input
                                    placeholder="City (e.g. Köln)"
                                    value={city}
                                    onChange={(e) => { setCity(e.target.value); }}
                                    onKeyDown={handleKeyDown}
                                    disabled={isSearching}
                                />
                            </div>
                        </div>
                    )}

                    {searchMode === "coordinates" && (
                        <div className="space-y-2">
                            <div className="grid grid-cols-2 gap-4">
                                <Input
                                    placeholder="Latitude (e.g. 50.9413)"
                                    value={latitude}
                                    onChange={(e) => { setLatitude(e.target.value); }}
                                    onKeyDown={handleKeyDown}
                                    disabled={isSearching}
                                />
                                <Input
                                    placeholder="Longitude (e.g. 6.9578)"
                                    value={longitude}
                                    onChange={(e) => { setLongitude(e.target.value); }}
                                    onKeyDown={handleKeyDown}
                                    disabled={isSearching}
                                />
                            </div>
                            {getCoordinateError() && (
                                <p className="text-sm text-destructive">{getCoordinateError()}</p>
                            )}
                        </div>
                    )}

                    {searchMode === "dno" && (
                        <div className="space-y-2">
                            <Input
                                placeholder="DNO Name (e.g. Netze BW, RheinEnergie, Westnetz)"
                                value={dnoName}
                                onChange={(e) => { setDnoName(e.target.value); }}
                                onKeyDown={handleKeyDown}
                                disabled={isSearching}
                            />
                            <p className="text-xs text-muted-foreground">
                                Fuzzy search - partial names work (e.g. "Netze" will match "Netze BW GmbH")
                            </p>
                        </div>
                    )}

                    <div className="border rounded-lg overflow-hidden">
                        <button
                            type="button"
                            onClick={() => { setFiltersExpanded(!filtersExpanded); }}
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
                                                onClick={() => { toggleYear(year); }}
                                                className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm font-medium transition-colors ${isSelected
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-background border-input hover:bg-muted"
                                                    }`}
                                            >
                                                <div className={`w-4 h-4 rounded border flex items-center justify-center ${isSelected
                                                    ? "bg-primary-foreground/20 border-primary-foreground/50"
                                                    : "border-current opacity-50"
                                                    }`}>
                                                    {isSelected && <Check className="w-3 h-3" />}
                                                </div>
                                                {year}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>

                    <Button
                        onClick={handleSearch}
                        disabled={!canSearch || isSearching}
                        className="w-full gap-2"
                        size="lg"
                    >
                        {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        Search
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <Alert variant="destructive" className={errorClassName}>
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            {result && (
                <Card className={resultClassName}>
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
                                {result.location && (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <MapPin className="w-4 h-4" />
                                        {result.location.street}, {result.location.zip_code} {result.location.city}
                                    </div>
                                )}

                                {result.has_data ? (
                                    <DataPreviewTables
                                        netzentgelte={result.netzentgelte}
                                        hlzf={result.hlzf}
                                        dnoId={result.dno.id}
                                        dnoSlug={result.dno.slug}
                                        showManageLink={true}
                                    />
                                ) : showImportLinkForSkeleton ? (
                                    <div className="space-y-4">
                                        <Alert>
                                            <AlertCircle className="h-4 w-4" />
                                            <AlertTitle>No data yet</AlertTitle>
                                            <AlertDescription>
                                                {result.message || "This DNO has been registered but no data has been crawled yet."}
                                            </AlertDescription>
                                        </Alert>
                                        <Button asChild className="w-full gap-2">
                                            <Link to={`/dnos/${result.dno.id || result.dno.slug}`}>
                                                Import Data
                                                <ArrowRight className="w-4 h-4" />
                                            </Link>
                                        </Button>
                                    </div>
                                ) : (
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
        </>
    );
}
