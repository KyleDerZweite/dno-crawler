import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Netzentgelte } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Search, Loader2, Zap, Calendar } from "lucide-react";

export function SearchPage() {
  const [postalCode, setPostalCode] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const {
    data: resultsResponse,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["search", searchQuery],
    queryFn: () => api.public.searchData({ dno: searchQuery }), // Adapting to use the API properly
    enabled: !!searchQuery,
  });

  const results = resultsResponse?.data as Netzentgelte[] | undefined;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (postalCode.trim()) {
      setSearchQuery(postalCode.trim());
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Search Data</h1>
        <p className="text-muted-foreground mt-1">
          Find electricity network charges by postal code or DNO
        </p>
      </div>

      {/* Search Input */}
      <Card className="p-4">
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Enter DNO name or ID (Postal code search coming soon)"
              value={postalCode}
              onChange={(e) => setPostalCode(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button type="submit" disabled={isLoading || !postalCode.trim()}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              "Search"
            )}
          </Button>
        </form>
      </Card>

      {/* Results */}
      {error && (
        <div className="bg-error/10 border border-error/20 rounded-xl p-6">
          <p className="text-error text-center">
            Error searching: {(error as Error).message}
          </p>
        </div>
      )}

      {searchQuery && !isLoading && results && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground">
            Results for "{searchQuery}"
            <span className="text-muted-foreground font-normal ml-2">
              ({results.length} found)
            </span>
          </h2>

          {results.length === 0 ? (
            <div className="text-center py-12">
              <Card className="rounded-2xl p-8 max-w-md mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-secondary border border-border flex items-center justify-center mx-auto mb-4">
                  <Search className="w-8 h-8 text-muted-foreground" />
                </div>
                <p className="text-muted-foreground">
                  No network charges found.
                </p>
              </Card>
            </div>
          ) : (
            <div className="grid gap-4">
              {results.map((result, index) => (
                <NetzentgelteCard key={index} data={result} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!searchQuery && (
        <Card className="text-center py-16 border-dashed">
          <CardContent>
            <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4 shadow-glow">
              <Zap className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold text-foreground mb-2">
              Discover Data
            </h3>
            <p className="text-muted-foreground">
              Enter a search term above to find network charges.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function NetzentgelteCard({ data }: { data: Netzentgelte }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{data.dno_id || "Unknown DNO"}</CardTitle>
            <CardDescription className="flex items-center gap-1 mt-1">
              <Calendar className="h-3 w-3" />
              Year: {data.year}
            </CardDescription>
          </div>
          <div className="flex items-center gap-1 text-sm font-medium text-primary bg-primary/10 px-2 py-1 rounded">
            {data.voltage_level}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <PriceItem label="Leistungspreis" value={data.leistung} unit="€/kW" />
          <PriceItem label="Arbeitspreis" value={data.arbeit} unit="ct/kWh" />
        </div>
      </CardContent>
    </Card>
  );
}

function PriceItem({
  label,
  value,
  unit,
}: {
  label: string;
  value?: number | null;
  unit: string;
}) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold flex items-center gap-1">
        {value != null ? (
          <>
            {value.toFixed(4)}
            <span className="text-sm font-normal text-muted-foreground">{unit}</span>
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </p>
    </div>
  );
}