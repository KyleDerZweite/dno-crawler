/**
 * DetailContextSidebar - DNO-specific Context Sidebar
 * 
 * Displays:
 * - Entity header (icon, name, region)
 * - Quick actions (website, edit, crawl trigger)
 * - Vertical nav links for sub-views
 * - Completeness footer
 */

import { NavLink } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Zap,
    LayoutDashboard,
    Table as TableIcon,
    BarChart3,
    FileText,
    History,
    Wrench,
    ExternalLink,
    Pencil,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CrawlDialog } from "./CrawlDialog";
import type { DNO } from "@/lib/api";

interface NavItem {
    id: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    path: string;
    count?: number;
}

interface DetailContextSidebarProps {
    dno: DNO;
    basePath: string;
    isAdmin: boolean;
    filesCount: number;
    jobsCount: number;
    completeness: {
        percentage: number;
        voltageLevels: number;
        years: number;
    };
    onEditClick: () => void;
    onTriggerCrawl: (params: {
        years: number[];
        dataType: "all" | "netzentgelte" | "hlzf";
        jobType: "full" | "crawl" | "extract";
    }) => void;
    isCrawlPending: boolean;
}

export function DetailContextSidebar({
    dno,
    basePath,
    isAdmin,
    filesCount,
    jobsCount,
    completeness,
    onEditClick,
    onTriggerCrawl,
    isCrawlPending,
}: DetailContextSidebarProps) {
    const navItems: NavItem[] = [
        { id: "overview", label: "Overview", icon: LayoutDashboard, path: `${basePath}/overview` },
        { id: "data", label: "Data Explorer", icon: TableIcon, path: `${basePath}/data` },
        { id: "analysis", label: "Analysis", icon: BarChart3, path: `${basePath}/analysis` },
        { id: "files", label: "Source Files", icon: FileText, path: `${basePath}/files`, count: filesCount },
        { id: "jobs", label: "Job History", icon: History, path: `${basePath}/jobs`, count: jobsCount },
        { id: "tools", label: "Tools", icon: Wrench, path: `${basePath}/tools` },
    ];

    return (
        <aside className="w-72 border-r bg-muted/10 flex flex-col shrink-0">
            {/* Entity Header */}
            <div className="p-6 border-b">
                <div className="flex items-center gap-3 mb-4">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                        <Zap className="h-6 w-6" />
                    </div>
                    <div className="overflow-hidden">
                        <h1 className="font-bold text-lg truncate leading-tight" title={dno.name}>
                            {dno.name}
                        </h1>
                        <p className="text-xs text-muted-foreground truncate">
                            {dno.region || "Unknown Region"}
                        </p>
                    </div>
                </div>

                {/* Quick Actions */}
                <div className="flex gap-1 justify-between">
                    {dno.website && (
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" asChild title="Website">
                            <a href={dno.website} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-4 w-4" />
                            </a>
                        </Button>
                    )}
                    {isAdmin && (
                        <>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={onEditClick} title="Edit Metadata">
                                <Pencil className="h-4 w-4" />
                            </Button>
                            <div className="h-8 w-[1px] bg-border mx-1 my-auto"></div>
                        </>
                    )}
                    <CrawlDialog
                        dnoName={dno.name}
                        crawlable={dno.crawlable !== false}
                        hasLocalFiles={!!dno.has_local_files}
                        onTrigger={onTriggerCrawl}
                        isPending={isCrawlPending}
                    />
                </div>
            </div>

            {/* Vertical Tabs */}
            <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
                {navItems.map(item => (
                    <NavLink
                        key={item.id}
                        to={item.path}
                        className={({ isActive }) => cn(
                            "flex items-center w-full gap-3 px-3 py-2 text-sm font-medium rounded-md transition-all",
                            isActive
                                ? "bg-primary/10 text-primary"
                                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                        )}
                    >
                        <item.icon className="h-4 w-4 shrink-0" />
                        <span className="flex-1 text-left">{item.label}</span>
                        {item.count !== undefined && item.count > 0 && (
                            <Badge variant="secondary" className="ml-auto text-[10px] h-5 px-1.5 min-w-[1.25rem] flex items-center justify-center">
                                {item.count}
                            </Badge>
                        )}
                    </NavLink>
                ))}
            </nav>

            {/* Meta Footer */}
            <div className="p-4 border-t bg-muted/5">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Completeness</span>
                    <span className="text-xs font-bold">{completeness.percentage.toFixed(0)}%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div
                        className={cn("h-full rounded-full transition-all",
                            completeness.percentage >= 80 ? "bg-green-500" :
                                completeness.percentage >= 50 ? "bg-amber-500" : "bg-red-500"
                        )}
                        style={{ width: `${completeness.percentage}%` }}
                    />
                </div>
                <p className="text-[10px] text-muted-foreground mt-2">
                    {completeness.voltageLevels} levels available for {completeness.years} years
                </p>
            </div>
        </aside>
    );
}
