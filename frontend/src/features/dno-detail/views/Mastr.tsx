import { useOutletContext } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { DNODetailContext } from "./types";
import { formatDate, formatDateTime, formatNumber } from "../utils/data-utils";

const VOLTAGE_LABELS: Record<string, string> = {
    ns: "NS",
    ms: "MS",
    hs: "HS",
    hoe: "HöS",
};

function formatCount(value?: number | null): string {
    if (value === null || value === undefined) {
        return "-";
    }
    return formatNumber(value, 0);
}

function formatCapacity(value?: number | null): string {
    if (value === null || value === undefined) {
        return "-";
    }
    return `${formatNumber(value, 2)} MW`;
}

export function Mastr() {
    const { dno } = useOutletContext<DNODetailContext>();

    const mastrData = dno.mastr_data;
    const stats = dno.stats;

    if (!mastrData && !stats) {
        return (
            <Card className="p-8 text-center text-muted-foreground">
                <p className="text-lg font-medium mb-2">No MaStR data available</p>
                <p className="text-sm">
                    This DNO currently has no imported MaStR source payload or computed MaStR statistics.
                </p>
            </Card>
        );
    }

    const byVoltage = stats?.connection_points?.by_voltage;
    const byCanonicalLevel = stats?.connection_points?.by_canonical_level;
    const canonicalEntries = byCanonicalLevel
        ? Object.entries(byCanonicalLevel).sort((a, b) => a[0].localeCompare(b[0]))
        : [];

    const capacity = stats?.installed_capacity_mw;
    const unitCounts = stats?.unit_counts;

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h2 className="text-xl font-semibold">MaStR View</h2>
                    <p className="text-sm text-muted-foreground">
                        Source attributes and aggregated MaStR statistics for this DNO.
                    </p>
                </div>
                <Badge variant={dno.has_mastr ? "default" : "secondary"}>
                    {dno.has_mastr ? "Source Available" : "No Source Link"}
                </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <Card className="p-4">
                    <p className="text-xs text-muted-foreground">MaStR Number</p>
                    <p className="text-lg font-semibold mt-1">{mastrData?.mastr_nr || dno.mastr_nr || "-"}</p>
                </Card>
                <Card className="p-4">
                    <p className="text-xs text-muted-foreground">Connection Points</p>
                    <p className="text-lg font-semibold mt-1">
                        {formatCount(stats?.connection_points?.total)}
                    </p>
                </Card>
                <Card className="p-4">
                    <p className="text-xs text-muted-foreground">Installed Capacity</p>
                    <p className="text-lg font-semibold mt-1">{formatCapacity(capacity?.total)}</p>
                </Card>
                <Card className="p-4">
                    <p className="text-xs text-muted-foreground">Data Quality</p>
                    <p className="text-lg font-semibold mt-1">{stats?.data_quality || "-"}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                        Computed: {formatDateTime(stats?.computed_at)}
                    </p>
                </Card>
            </div>

            {mastrData && (
                <Card className="p-4">
                    <h3 className="text-sm font-semibold mb-3">Source Metadata</h3>
                    <dl className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 text-sm">
                        <div>
                            <dt className="text-muted-foreground">Registered Name</dt>
                            <dd className="font-medium">{mastrData.registered_name || "-"}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">ACER Code</dt>
                            <dd className="font-medium">{mastrData.acer_code || "-"}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Region</dt>
                            <dd className="font-medium">{mastrData.region || "-"}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Registration Date</dt>
                            <dd className="font-medium">{formatDate(mastrData.registration_date)}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Activity Start</dt>
                            <dd className="font-medium">{formatDate(mastrData.activity_start)}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Activity End</dt>
                            <dd className="font-medium">{formatDate(mastrData.activity_end)}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Last Updated (MaStR)</dt>
                            <dd className="font-medium">{formatDate(mastrData.mastr_last_updated)}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Last Synced</dt>
                            <dd className="font-medium">{formatDateTime(mastrData.last_synced_at)}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Status</dt>
                            <dd>
                                <Badge variant={mastrData.is_active ? "default" : "secondary"}>
                                    {mastrData.is_active ? "Active" : "Inactive"}
                                </Badge>
                            </dd>
                        </div>
                    </dl>
                    {mastrData.marktrollen && mastrData.marktrollen.length > 0 && (
                        <div className="pt-4 mt-4 border-t">
                            <p className="text-xs text-muted-foreground mb-2">Market Roles</p>
                            <div className="flex flex-wrap gap-2">
                                {mastrData.marktrollen.map((role) => (
                                    <Badge key={role} variant="outline">
                                        {role}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    )}
                </Card>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <Card className="p-4">
                    <h3 className="text-sm font-semibold mb-3">Connection Points by Voltage</h3>
                    <div className="space-y-2 text-sm">
                        {Object.entries(VOLTAGE_LABELS).map(([key, label]) => (
                            <div key={key} className="flex items-center justify-between border-b border-border/50 pb-2 last:border-0 last:pb-0">
                                <span className="text-muted-foreground">{label}</span>
                                <span className="font-medium">{formatCount(byVoltage?.[key as keyof typeof byVoltage])}</span>
                            </div>
                        ))}
                    </div>
                </Card>

                <Card className="p-4">
                    <h3 className="text-sm font-semibold mb-3">Installed Capacity (MW)</h3>
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Solar</span>
                            <span className="font-medium">{formatCapacity(capacity?.solar)}</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Wind</span>
                            <span className="font-medium">{formatCapacity(capacity?.wind)}</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Storage</span>
                            <span className="font-medium">{formatCapacity(capacity?.storage)}</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Biomass</span>
                            <span className="font-medium">{formatCapacity(capacity?.biomass)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Hydro</span>
                            <span className="font-medium">{formatCapacity(capacity?.hydro)}</span>
                        </div>
                    </div>
                </Card>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <Card className="p-4">
                    <h3 className="text-sm font-semibold mb-3">Connection Points by Canonical Level</h3>
                    {canonicalEntries.length > 0 ? (
                        <div className="space-y-2 text-sm">
                            {canonicalEntries.map(([level, value]) => (
                                <div key={level} className="flex items-center justify-between border-b border-border/50 pb-2 last:border-0 last:pb-0">
                                    <span className="text-muted-foreground">{level}</span>
                                    <span className="font-medium">{formatCount(value)}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">No canonical level distribution available.</p>
                    )}
                </Card>

                <Card className="p-4">
                    <h3 className="text-sm font-semibold mb-3">Network and Unit Stats</h3>
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Networks</span>
                            <span className="font-medium">{formatCount(stats?.networks?.count)}</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Has Customers</span>
                            <span className="font-medium">
                                {stats?.networks?.has_customers === undefined || stats?.networks?.has_customers === null
                                    ? "-"
                                    : stats.networks.has_customers
                                        ? "Yes"
                                        : "No"}
                            </span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Closed Distribution Network</span>
                            <span className="font-medium">
                                {stats?.networks?.closed_distribution_network === undefined || stats?.networks?.closed_distribution_network === null
                                    ? "-"
                                    : stats.networks.closed_distribution_network
                                        ? "Yes"
                                        : "No"}
                            </span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Solar Units</span>
                            <span className="font-medium">{formatCount(unitCounts?.solar)}</span>
                        </div>
                        <div className="flex items-center justify-between border-b border-border/50 pb-2">
                            <span className="text-muted-foreground">Wind Units</span>
                            <span className="font-medium">{formatCount(unitCounts?.wind)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Storage Units</span>
                            <span className="font-medium">{formatCount(unitCounts?.storage)}</span>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}
