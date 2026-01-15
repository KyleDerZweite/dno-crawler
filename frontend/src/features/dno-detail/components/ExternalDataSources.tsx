/**
 * ExternalDataSources - Section showing external data sources
 * Displays MaStR, VNB Digital, and BDEW data when available
 */

import { Badge } from "@/components/ui/badge";
import { Database, Globe, Building } from "lucide-react";
import { cn } from "@/lib/utils";

interface MaStRData {
    mastr_nr: string;
    acer_code?: string;
    region?: string;
    marktrollen?: string[];
    is_active?: boolean;
    closed_network?: boolean;
    registration_date?: string;
    contact_address?: string;
}

interface VNBData {
    vnb_id: string;
    official_name?: string;
    homepage_url?: string;
    phone?: string;
    email?: string;
    address?: string;
    types?: string[];
    voltage_types?: string[];
}

interface BDEWData {
    bdew_code: string;
    market_function?: string;
    is_grid_operator?: boolean;
    region?: string;
}

interface SourceDataAccordionProps {
    hasMastr: boolean;
    hasVnb: boolean;
    hasBdew: boolean;
    mastrData?: MaStRData;
    vnbData?: VNBData;
    bdewData?: BDEWData[];
}

export function ExternalDataSources({
    hasMastr,
    hasVnb,
    hasBdew,
    mastrData,
    vnbData,
    bdewData,
}: SourceDataAccordionProps) {
    // Don't render if no external data
    if (!mastrData && !vnbData && (!bdewData || bdewData.length === 0)) {
        return null;
    }

    return (
        <div className="p-4 space-y-4">
            {/* Source Availability Badges */}
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">Data Sources:</span>
                <Badge
                    variant={hasMastr ? "default" : "outline"}
                    className={cn("text-xs", hasMastr && "bg-purple-500")}
                >
                    MaStR {hasMastr ? "✓" : "–"}
                </Badge>
                <Badge
                    variant={hasVnb ? "default" : "outline"}
                    className={cn("text-xs", hasVnb && "bg-blue-500")}
                >
                    VNB Digital {hasVnb ? "✓" : "–"}
                </Badge>
                <Badge
                    variant={hasBdew ? "default" : "outline"}
                    className={cn("text-xs", hasBdew && "bg-green-500")}
                >
                    BDEW {hasBdew ? "✓" : "–"}
                </Badge>
            </div>

            {/* External Data Content - Always Visible */}
            <div className="space-y-4 pt-4 border-t border-border">
                {/* MaStR Data Section */}
                {mastrData && (
                    <div className="rounded-lg border border-purple-200 bg-purple-50/50 dark:border-purple-800 dark:bg-purple-950/20 p-3">
                        <h4 className="text-xs font-semibold text-purple-700 dark:text-purple-300 mb-2 flex items-center gap-1">
                            <Database className="h-3 w-3" /> MaStR (Marktstammdatenregister)
                        </h4>
                        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm">
                            <div className="flex justify-between sm:block">
                                <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                    MaStR Nr.
                                </dt>
                                <dd className="font-mono inline text-xs">{mastrData.mastr_nr}</dd>
                            </div>
                            {mastrData.acer_code && (
                                <div className="flex justify-between sm:block">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        ACER Code
                                    </dt>
                                    <dd className="font-mono inline text-xs">{mastrData.acer_code}</dd>
                                </div>
                            )}
                            {mastrData.region && (
                                <div className="flex justify-between sm:block">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        Region
                                    </dt>
                                    <dd className="inline text-xs">{mastrData.region}</dd>
                                </div>
                            )}
                            {mastrData.marktrollen && mastrData.marktrollen.length > 0 && (
                                <div className="flex justify-between sm:block sm:col-span-full">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        Market Roles
                                    </dt>
                                    <dd className="inline">
                                        <div className="flex flex-wrap gap-1 mt-1 sm:mt-0 sm:inline-flex">
                                            {mastrData.marktrollen.map((role, idx) => (
                                                <Badge key={idx} variant="outline" className="text-xs">
                                                    {role}
                                                </Badge>
                                            ))}
                                        </div>
                                    </dd>
                                </div>
                            )}
                            {mastrData.is_active !== undefined && (
                                <div className="flex justify-between sm:block">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        Status
                                    </dt>
                                    <dd className="inline">
                                        <Badge
                                            variant={mastrData.is_active ? "default" : "secondary"}
                                            className="text-xs"
                                        >
                                            {mastrData.is_active ? "Active" : "Inactive"}
                                        </Badge>
                                    </dd>
                                </div>
                            )}
                        </dl>
                    </div>
                )}

                {/* VNB Digital Data Section */}
                {vnbData && (
                    <div className="rounded-lg border border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/20 p-3">
                        <h4 className="text-xs font-semibold text-blue-700 dark:text-blue-300 mb-2 flex items-center gap-1">
                            <Globe className="h-3 w-3" /> VNB Digital
                        </h4>
                        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm">
                            <div className="flex justify-between sm:block">
                                <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                    VNB ID
                                </dt>
                                <dd className="font-mono inline text-xs">{vnbData.vnb_id}</dd>
                            </div>
                            {vnbData.official_name && (
                                <div className="flex justify-between sm:block sm:col-span-2">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        Official Name
                                    </dt>
                                    <dd className="inline text-xs">{vnbData.official_name}</dd>
                                </div>
                            )}
                            {vnbData.phone && (
                                <div className="flex justify-between sm:block">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        Phone
                                    </dt>
                                    <dd className="inline">
                                        <a
                                            href={`tel:${vnbData.phone}`}
                                            className="text-primary hover:underline text-xs"
                                        >
                                            {vnbData.phone}
                                        </a>
                                    </dd>
                                </div>
                            )}
                            {vnbData.email && (
                                <div className="flex justify-between sm:block">
                                    <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                        Email
                                    </dt>
                                    <dd className="inline">
                                        <a
                                            href={`mailto:${vnbData.email}`}
                                            className="text-primary hover:underline text-xs"
                                        >
                                            {vnbData.email}
                                        </a>
                                    </dd>
                                </div>
                            )}
                        </dl>
                    </div>
                )}

                {/* BDEW Data Section */}
                {bdewData && bdewData.length > 0 && (
                    <div className="rounded-lg border border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/20 p-3">
                        <h4 className="text-xs font-semibold text-green-700 dark:text-green-300 mb-2 flex items-center gap-1">
                            <Building className="h-3 w-3" /> BDEW Codes ({bdewData.length})
                        </h4>
                        <div className="space-y-3">
                            {bdewData.map((bdew, idx) => (
                                <dl
                                    key={idx}
                                    className={cn(
                                        "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-sm",
                                        idx > 0 && "pt-3 border-t border-green-200 dark:border-green-800"
                                    )}
                                >
                                    <div className="flex justify-between sm:block">
                                        <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                            BDEW Code
                                        </dt>
                                        <dd className="font-mono inline text-xs">{bdew.bdew_code}</dd>
                                    </div>
                                    {bdew.market_function && (
                                        <div className="flex justify-between sm:block">
                                            <dt className="text-muted-foreground inline sm:inline-block sm:w-24">
                                                Market Role
                                            </dt>
                                            <dd className="inline">
                                                <Badge
                                                    variant="outline"
                                                    className={cn(
                                                        "text-xs",
                                                        bdew.market_function === "Netzbetreiber" &&
                                                        "border-green-400 text-green-700 dark:text-green-300"
                                                    )}
                                                >
                                                    {bdew.market_function}
                                                </Badge>
                                            </dd>
                                        </div>
                                    )}
                                </dl>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

