/**
 * Technical View - Sitemap URLs, robots.txt data, and crawl metadata
 * 
 * ============================================================================
 * PURPOSE
 * ============================================================================
 * This view provides advanced users with technical crawl data for a DNO:
 * - Robots.txt information (raw content, disallow paths, fetch status)
 * - Sitemap URLs with filtering, search, and relevance scoring
 * - Crawl metadata (last fetched timestamps, TTL status)
 * 
 * ============================================================================
 * LAYOUT STRUCTURE
 * ============================================================================
 * 
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  📊 Crawl Metadata                                                      │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ Robots.txt: ✅ Available    │  Sitemap: ✅ 760 URLs                 │
 * │  │ Last checked: 2 days ago    │  Crawlable: ✅ Yes                    │
 * │  │ TTL: 148 days remaining     │  Language: de (German)                │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * │                                                                         │
 * │  🔍 Sitemap URLs (760 total)                                            │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ Filters:                                                             │
 * │  │ [Search: _______________] [Type: All ▼] [Year: Any ▼]               │
 * │  │ [Keywords: netzentgelt, preisblatt, hlzf ▼]                         │
 * │  ├─────────────────────────────────────────────────────────────────────┤
 * │  │ URL                                        │ Type │ Score │ Year   │
 * │  ├────────────────────────────────────────────┼──────┼───────┼────────┤
 * │  │ /de/downloads/netzentgelte-2025.pdf        │ PDF  │  85   │ 2025   │
 * │  │ /de/downloads/preisblatt-strom.pdf         │ PDF  │  70   │ -      │
 * │  │ /de/service/downloads                      │ HTML │  30   │ -      │
 * │  │ ...                                        │      │       │        │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * │  Pagination: [< Prev] Page 1 of 15 [Next >]                            │
 * │                                                                         │
 * │  📋 Disallow Paths (collapsed by default)                          [▼] │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ /admin/                                                             │
 * │  │ /api/internal/                                                      │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * │                                                                         │
 * │  📜 Raw robots.txt (collapsed by default)                          [▼] │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ User-agent: *                                                       │
 * │  │ Disallow: /admin/                                                   │
 * │  │ Sitemap: https://example.com/de/sitemap.xml                         │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * └─────────────────────────────────────────────────────────────────────────┘
 * 
 * ============================================================================
 * DATA SOURCES
 * ============================================================================
 * From DNO model:
 * - robots_txt: Raw robots.txt content
 * - robots_fetched_at: Timestamp (TTL: 150 days)
 * - sitemap_urls: Sitemap URLs from robots.txt
 * - sitemap_parsed_urls: All URLs extracted from sitemaps
 * - sitemap_fetched_at: Timestamp (TTL: 120 days)
 * - disallow_paths: Blocked paths
 * - crawlable: Boolean
 * - crawl_blocked_reason: Why blocked (if any)
 * 
 * ============================================================================
 * FEATURES TO IMPLEMENT
 * ============================================================================
 * 1. Metadata Cards
 *    - Robots status with TTL indicator (days remaining)
 *    - Sitemap status with URL count
 *    - Crawlability badge
 * 
 * 2. Sitemap URL Table
 *    - Search filter (text search in URL)
 *    - File type filter (PDF, HTML, XLSX, All)
 *    - Year filter (extract years from URLs)
 *    - Keyword filter (netzentgelt, preisblatt, hlzf, etc.)
 *    - Relevance score column (use discovery scorer logic)
 *    - Sortable columns
 *    - Pagination (50 per page)
 *    - Export to CSV
 * 
 * 3. Collapsible Sections
 *    - Disallow paths list
 *    - Raw robots.txt content (monospace font)
 * 
 * ============================================================================
 * API ENDPOINTS NEEDED
 * ============================================================================
 * The existing GET /api/dnos/{id} should already return:
 * - sitemap_parsed_urls (array of strings)
 * - robots_txt (string)
 * - disallow_paths (array of strings)
 * - sitemap_fetched_at (ISO timestamp)
 * - robots_fetched_at (ISO timestamp)
 * 
 * If not, we need to extend the DNO detail response.
 * 
 * ============================================================================
 * COMPONENTS TO USE
 * ============================================================================
 * - Card, CardHeader, CardContent (for metadata cards)
 * - Input (for search)
 * - Select (for filters)
 * - Table, TableHeader, TableBody, TableRow, TableCell
 * - Badge (for status indicators)
 * - Collapsible (for optional sections)
 * - Button (for export, pagination)
 */

import { useOutletContext } from "react-router-dom";
import type { DNODetailContext } from "./types";

export function Technical() {
    const { dno } = useOutletContext<DNODetailContext>();

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-semibold">Technical Data</h1>
                <p className="text-muted-foreground">
                    Crawl metadata, sitemap URLs, and robots.txt information
                </p>
            </div>

            {/* TODO: Implement metadata cards */}
            <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">
                <p className="text-lg font-medium mb-2">Technical View</p>
                <p className="text-sm">
                    This page will display sitemap URLs ({dno.sitemap_parsed_urls?.length || 0} URLs),
                    robots.txt data, and crawl metadata.
                </p>
                <p className="text-sm mt-2">
                    See component file for detailed implementation plan.
                </p>
            </div>
        </div>
    );
}
