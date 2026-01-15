/**
 * Analysis View - Placeholder for Charts and Data Analysis
 */

import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { BarChart3, Clock, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DNODetailContext } from "./types";

export function Analysis() {
    const { numericId } = useOutletContext<DNODetailContext>();

    // Fetch data for completeness matrix
    const { data: dataResponse } = useQuery({
        queryKey: ["dno-data", numericId],
        queryFn: () => api.dnos.getData(String(numericId)),
        enabled: !!numericId,
    });

    const netzentgelte = dataResponse?.data?.netzentgelte || [];

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="p-6 h-[300px] flex items-center justify-center border-dashed">
                    <div className="text-center">
                        <BarChart3 className="h-10 w-10 text-muted-foreground mx-auto mb-2 opacity-50" />
                        <h3 className="font-semibold text-muted-foreground">Price Trends</h3>
                        <p className="text-sm text-muted-foreground/70">Chart visualization coming soon</p>
                    </div>
                </Card>
                <Card className="p-6 h-[300px] flex items-center justify-center border-dashed">
                    <div className="text-center">
                        <Clock className="h-10 w-10 text-muted-foreground mx-auto mb-2 opacity-50" />
                        <h3 className="font-semibold text-muted-foreground">HLZF Heatmap</h3>
                        <p className="text-sm text-muted-foreground/70">Visualization of peak times coming soon</p>
                    </div>
                </Card>
            </div>
            <Card className="p-6">
                <h3 className="font-semibold mb-4">Data Completeness Matrix</h3>
                <div className="grid grid-cols-6 gap-2 text-center text-sm">
                    <div className="font-medium text-left text-muted-foreground">Year</div>
                    {['2020', '2021', '2022', '2023', '2024'].map(y => (
                        <div key={y} className="font-medium text-muted-foreground">{y}</div>
                    ))}
                    {['HS', 'HS/MS', 'MS', 'MS/NS', 'NS'].map(v => (
                        <>
                            <div key={`label-${v}`} className="text-left font-medium">{v}</div>
                            {['2020', '2021', '2022', '2023', '2024'].map(y => {
                                const hasData = netzentgelte.some((n: any) => n.year === parseInt(y) && n.voltage_level === v);
                                return (
                                    <div key={`${v}-${y}`} className="flex justify-center">
                                        <div className={cn("h-6 w-6 rounded-md flex items-center justify-center", hasData ? "bg-green-100 text-green-600" : "bg-gray-100 text-gray-300")}>
                                            {hasData ? <Check className="h-3 w-3" /> : "•"}
                                        </div>
                                    </div>
                                );
                            })}
                        </>
                    ))}
                </div>
            </Card>
        </div>
    );
}
