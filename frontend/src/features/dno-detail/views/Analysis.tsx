/**
 * Analysis View - Charts and Data Analysis
 * Features: Price trends, HLZF timeline, data completeness heatmap
 */

import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import type { DNODetailContext } from "./types";
import {
    PriceTrendChart,
    HLZFTimelineChart,
    DataCompletenessHeatmap,
} from "../components";

export function Analysis() {
    const { numericId } = useOutletContext<DNODetailContext>();

    // Fetch data for charts
    const { data: dataResponse, isLoading } = useQuery({
        queryKey: ["dno-data", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: !!numericId,
    });

    const netzentgelte = dataResponse?.data?.netzentgelte || [];
    const hlzf = dataResponse?.data?.hlzf || [];

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* Price Trends - Full width */}
            <Card className="p-6">
                <PriceTrendChart
                    netzentgelte={netzentgelte}
                    isLoading={isLoading}
                />
            </Card>

            {/* HLZF Timeline - Full width */}
            <Card className="p-6">
                <HLZFTimelineChart
                    hlzf={hlzf}
                    isLoading={isLoading}
                />
            </Card>

            {/* Data Completeness Heatmap - Full width */}
            <Card className="p-6">
                <DataCompletenessHeatmap
                    netzentgelte={netzentgelte}
                    hlzf={hlzf}
                    isLoading={isLoading}
                />
            </Card>
        </div>
    );
}
