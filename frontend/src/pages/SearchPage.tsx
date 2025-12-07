import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type DNO, type Netzentgelte } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, Loader2, Zap, Copy, Check, Database } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export function SearchPage() {
  const [selectedDnoId, setSelectedDnoId] = useState<string>("");
  const [selectedYear, setSelectedYear] = useState<string>("");
  const [copiedCell, setCopiedCell] = useState<string | null>(null);
  const { toast } = useToast();

  // Fetch DNO list
  const { data: dnosResponse, isLoading: dnosLoading } = useQuery({
    queryKey: ["dnos-list"],
    queryFn: () => api.dnos.list(),
  });

  const dnos = dnosResponse?.data || [];

  // Fetch available years
  const { data: yearsResponse } = useQuery({
    queryKey: ["available-years", selectedDnoId],
    queryFn: () => api.public.getYears(selectedDnoId ? dnos.find(d => d.id === selectedDnoId)?.slug : undefined),
    enabled: true,
  });

  const years = yearsResponse?.data || [];

  // Fetch netzentgelte data when DNO is selected
  const { data: dataResponse, isLoading: dataLoading } = useQuery({
    queryKey: ["netzentgelte-data", selectedDnoId, selectedYear],
    queryFn: () => api.public.searchData({
      dno: dnos.find(d => d.id === selectedDnoId)?.slug,
      year: selectedYear ? parseInt(selectedYear) : undefined,
      data_type: "netzentgelte",
    }),
    enabled: !!selectedDnoId,
  });

  const netzentgelte = (dataResponse?.data as Netzentgelte[] | undefined) || [];

  // Copy to clipboard handler
  const handleCellClick = useCallback((value: string | number | undefined | null, cellId: string) => {
    if (value == null) return;

    const textValue = typeof value === 'number' ? value.toString() : value;
    navigator.clipboard.writeText(textValue).then(() => {
      setCopiedCell(cellId);
      toast({
        title: "Copied!",
        description: `"${textValue}" copied to clipboard`,
        duration: 1500,
      });
      setTimeout(() => setCopiedCell(null), 1500);
    });
  }, [toast]);

  const selectedDno = dnos.find(d => d.id === selectedDnoId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Search Data</h1>
        <p className="text-muted-foreground mt-1">
          Find and copy electricity network charges by DNO and year
        </p>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-4 items-end">
          {/* DNO Selector */}
          <div className="flex-1 min-w-[200px]">
            <label className="text-sm font-medium text-muted-foreground block mb-2">
              Distribution Network Operator
            </label>
            <Select value={selectedDnoId} onValueChange={setSelectedDnoId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select DNO..." />
              </SelectTrigger>
              <SelectContent>
                {dnos.map((dno) => (
                  <SelectItem key={dno.id} value={dno.id}>
                    <div className="flex items-center gap-2">
                      <Database className="h-4 w-4 text-primary" />
                      {dno.name}
                      {dno.netzentgelte_count ? (
                        <span className="text-xs text-muted-foreground">
                          ({dno.netzentgelte_count} records)
                        </span>
                      ) : null}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Year Selector */}
          <div className="w-[140px]">
            <label className="text-sm font-medium text-muted-foreground block mb-2">
              Year
            </label>
            <Select
              value={selectedYear}
              onValueChange={setSelectedYear}
              disabled={!selectedDnoId}
            >
              <SelectTrigger>
                <SelectValue placeholder="All years" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All years</SelectItem>
                {years.map((year) => (
                  <SelectItem key={year} value={year.toString()}>
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Clear button */}
          {selectedDnoId && (
            <Button
              variant="outline"
              onClick={() => {
                setSelectedDnoId("");
                setSelectedYear("");
              }}
            >
              Clear
            </Button>
          )}
        </div>
      </Card>

      {/* Results */}
      {!selectedDnoId ? (
        <Card className="text-center py-16 border-dashed">
          <CardContent>
            <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4 shadow-glow">
              <Zap className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold text-foreground mb-2">
              Select a DNO
            </h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Choose a Distribution Network Operator from the dropdown above to view their Netzentgelte data.
              <br />
              <span className="text-sm">Click any cell to copy its value.</span>
            </p>
          </CardContent>
        </Card>
      ) : dataLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : netzentgelte.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <Search className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">
              No data found
            </h3>
            <p className="text-muted-foreground">
              No Netzentgelte records found for {selectedDno?.name}
              {selectedYear && ` in ${selectedYear}`}.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="p-4 border-b bg-muted/30">
            <h2 className="font-semibold flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Netzentgelte - {selectedDno?.name}
              {selectedYear && ` (${selectedYear})`}
              <span className="text-sm font-normal text-muted-foreground ml-2">
                {netzentgelte.length} records • Click cell to copy
              </span>
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground border-b">
                    Voltage Level
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground border-b">
                    Year
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground border-b whitespace-nowrap">
                    T&lt;2500 LP (€/kW)
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground border-b whitespace-nowrap">
                    T&lt;2500 AP (ct/kWh)
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground border-b whitespace-nowrap">
                    T≥2500 LP (€/kW)
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground border-b whitespace-nowrap">
                    T≥2500 AP (ct/kWh)
                  </th>
                </tr>
              </thead>
              <tbody>
                {netzentgelte.map((row, idx) => (
                  <tr key={idx} className="border-b border-border/50 hover:bg-muted/30">
                    <CopyableCell
                      value={row.voltage_level}
                      cellId={`${idx}-vl`}
                      copiedCell={copiedCell}
                      onClick={handleCellClick}
                    />
                    <CopyableCell
                      value={row.year}
                      cellId={`${idx}-year`}
                      copiedCell={copiedCell}
                      onClick={handleCellClick}
                    />
                    <CopyableCell
                      value={row.leistung_unter_2500h}
                      cellId={`${idx}-lp2500`}
                      copiedCell={copiedCell}
                      onClick={handleCellClick}
                      isNumber
                      decimals={2}
                    />
                    <CopyableCell
                      value={row.arbeit_unter_2500h}
                      cellId={`${idx}-ap2500`}
                      copiedCell={copiedCell}
                      onClick={handleCellClick}
                      isNumber
                      decimals={2}
                    />
                    <CopyableCell
                      value={row.leistung}
                      cellId={`${idx}-lp`}
                      copiedCell={copiedCell}
                      onClick={handleCellClick}
                      isNumber
                      decimals={2}
                    />
                    <CopyableCell
                      value={row.arbeit}
                      cellId={`${idx}-ap`}
                      copiedCell={copiedCell}
                      onClick={handleCellClick}
                      isNumber
                      decimals={2}
                    />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function CopyableCell({
  value,
  cellId,
  copiedCell,
  onClick,
  isNumber = false,
  decimals = 2,
}: {
  value: string | number | undefined | null;
  cellId: string;
  copiedCell: string | null;
  onClick: (value: string | number | undefined | null, cellId: string) => void;
  isNumber?: boolean;
  decimals?: number;
}) {
  const isCopied = copiedCell === cellId;

  const displayValue = value == null
    ? "—"
    : isNumber && typeof value === "number"
      ? value.toFixed(decimals)
      : value;

  return (
    <td
      className={cn(
        "py-3 px-4 cursor-pointer transition-colors relative group",
        isNumber && "text-right font-mono",
        isCopied && "bg-primary/10",
        value != null && "hover:bg-primary/5"
      )}
      onClick={() => onClick(value, cellId)}
      title={value != null ? "Click to copy" : undefined}
    >
      <span className={cn(value == null && "text-muted-foreground")}>
        {displayValue}
      </span>
      {value != null && (
        <span className={cn(
          "absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity",
          isCopied && "opacity-100"
        )}>
          {isCopied ? (
            <Check className="h-3 w-3 text-primary" />
          ) : (
            <Copy className="h-3 w-3 text-muted-foreground" />
          )}
        </span>
      )}
    </td>
  );
}