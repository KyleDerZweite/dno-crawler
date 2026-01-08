/**
 * DNOHeader - Header section for DNO detail page
 * Contains back navigation, DNO name, and action buttons
 */

import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft,
    Database,
    ExternalLink,
    Trash2,
    Pencil,
    AlertCircle,
} from "lucide-react";
import type { DNO } from "@/lib/api";

interface DNOHeaderProps {
    dno: DNO;
    isAdmin: boolean;
    onEditClick: () => void;
    onDeleteClick: () => void;
}

export function DNOHeader({
    dno,
    isAdmin,
    onEditClick,
    onDeleteClick,
}: DNOHeaderProps) {
    return (
        <div className="flex items-start justify-between">
            <div className="space-y-2">
                <Link
                    to="/dnos"
                    className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to DNOs
                </Link>
                <div className="flex items-center gap-3">
                    <div className="p-3 rounded-xl bg-primary/10 text-primary">
                        <Database className="h-6 w-6" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">{dno.name}</h1>
                        {dno.region && <p className="text-muted-foreground">{dno.region}</p>}
                    </div>
                </div>
            </div>
            <div className="flex gap-2 flex-wrap">
                {dno.website && (
                    <Button variant="outline" asChild>
                        <a href={dno.website} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="mr-2 h-4 w-4" />
                            Website
                        </a>
                    </Button>
                )}
                {isAdmin && (
                    <Button
                        variant="outline"
                        className="border-destructive text-destructive hover:bg-destructive/10"
                        onClick={onDeleteClick}
                    >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                    </Button>
                )}
                {isAdmin && (
                    <Button variant="outline" onClick={onEditClick}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                    </Button>
                )}

                {/* Crawlability warning badge */}
                {dno.crawlable === false && (
                    <Badge
                        variant="outline"
                        className="bg-amber-500/10 text-amber-600 border-amber-500/20 h-9 px-3"
                    >
                        <AlertCircle className="mr-1 h-3 w-3" />
                        {dno.crawl_blocked_reason === "cloudflare"
                            ? "Cloudflare Protected"
                            : dno.crawl_blocked_reason === "robots_disallow_all"
                                ? "Blocked by robots.txt"
                                : dno.crawl_blocked_reason || "Not Crawlable"}
                        {dno.has_local_files && " (Local files available)"}
                    </Badge>
                )}
            </div>
        </div>
    );
}
