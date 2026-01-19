/**
 * SQL Explorer View - Supabase-like SQL query interface for DNO data
 * 
 * ============================================================================
 * PURPOSE
 * ============================================================================
 * This view provides a SQL query interface for power users to:
 * - Explore raw database tables for a specific DNO
 * - Run custom SQL queries (read-only, scoped to DNO)
 * - Export query results to CSV/JSON
 * - Save and reuse common queries
 * 
 * ============================================================================
 * LAYOUT STRUCTURE
 * ============================================================================
 * 
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  📊 Quick Tables                           🔒 Scoped to DNO ID: 142     │
 * │  ┌──────────────┬──────────────┬──────────────┬──────────────┐         │
 * │  │ dnos (1)     │ netzentgelte │ hlzf (12)    │ crawl_jobs   │         │
 * │  │ [Click]      │ (24) [Click] │ [Click]      │ (8) [Click]  │         │
 * │  └──────────────┴──────────────┴──────────────┴──────────────┘         │
 * │  + data_sources │ source_profiles │                                    │
 * │                                                                         │
 * │  💻 SQL Query Editor                                                    │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ -- Query is auto-scoped to current DNO                              │
 * │  │ -- Available tables: netzentgelte, hlzf, crawl_jobs, data_sources   │
 * │  │                                                                     │
 * │  │ SELECT year, voltage_level, arbeit, leistung                        │
 * │  │ FROM netzentgelte                                                   │
 * │  │ WHERE dno_id = :dno_id  -- auto-injected                           │
 * │  │ ORDER BY year DESC, voltage_level                                   │
 * │  │                                                                     │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * │  [▶ Run Query (Ctrl+Enter)]  [📋 Copy]  [🗑 Clear]                      │
 * │                                                                         │
 * │  📋 Results (24 rows, 0.012s)                               [Export ▼] │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ year │ voltage_level              │ arbeit │ leistung              │
 * │  ├──────┼────────────────────────────┼────────┼───────────────────────┤
 * │  │ 2025 │ Niederspannung             │ 5.67   │ 42.30                 │
 * │  │ 2025 │ Mittelspannung             │ 3.21   │ 28.50                 │
 * │  │ 2024 │ Niederspannung             │ 5.45   │ 40.20                 │
 * │  │ ...  │ ...                        │ ...    │ ...                   │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * │  Showing 1-50 of 24 results                                            │
 * │                                                                         │
 * │  📑 Saved Queries                                              [▼]     │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ • Price history by year                              [Load] [Del]  │
 * │  │ • Compare voltage levels                             [Load] [Del]  │
 * │  │ • Failed crawl jobs                                  [Load] [Del]  │
 * │  │ [+ Save Current Query]                                             │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * │                                                                         │
 * │  📖 Schema Reference (collapsed)                               [▼]     │
 * │  ┌─────────────────────────────────────────────────────────────────────┤
 * │  │ netzentgelte: id, dno_id, year, voltage_level, arbeit, leistung... │
 * │  │ hlzf: id, dno_id, year, voltage_level, winter, sommer, herbst...   │
 * │  └─────────────────────────────────────────────────────────────────────┤
 * └─────────────────────────────────────────────────────────────────────────┘
 * 
 * ============================================================================
 * SECURITY MODEL
 * ============================================================================
 * 
 * 1. READ-ONLY: Only SELECT queries allowed
 *    - Block INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE
 *    - Validate query server-side before execution
 * 
 * 2. DNO-SCOPED: All queries are scoped to current DNO
 *    - Auto-inject dno_id parameter
 *    - Validate query only accesses allowed tables
 * 
 * 3. ALLOWED TABLES:
 *    - dnos (filtered to current DNO only)
 *    - netzentgelte (filtered by dno_id)
 *    - hlzf (filtered by dno_id)
 *    - crawl_jobs (filtered by dno_id)
 *    - crawl_job_steps (via job_id)
 *    - data_sources (filtered by dno_id)
 *    - dno_source_profiles (filtered by dno_id)
 * 
 * 4. LIMITS:
 *    - Max 1000 rows per query
 *    - Query timeout: 5 seconds
 *    - No subqueries to other DNOs
 * 
 * ============================================================================
 * API ENDPOINT NEEDED
 * ============================================================================
 * 
 * POST /api/dnos/{slug}/sql
 * 
 * Request:
 * {
 *   "query": "SELECT * FROM netzentgelte WHERE year = 2025 ORDER BY voltage_level",
 *   "limit": 100
 * }
 * 
 * Response:
 * {
 *   "columns": ["id", "year", "voltage_level", "arbeit", "leistung", ...],
 *   "rows": [
 *     [1, 2025, "Niederspannung", 5.67, 42.30, ...],
 *     [2, 2025, "Mittelspannung", 3.21, 28.50, ...],
 *     ...
 *   ],
 *   "row_count": 24,
 *   "execution_time_ms": 12,
 *   "truncated": false
 * }
 * 
 * Error Response:
 * {
 *   "error": "Query validation failed: UPDATE not allowed",
 *   "code": "INVALID_QUERY"
 * }
 * 
 * ============================================================================
 * PRESET QUERIES
 * ============================================================================
 * 
 * 1. "All Netzentgelte by Year"
 *    SELECT year, voltage_level, arbeit, leistung 
 *    FROM netzentgelte 
 *    WHERE dno_id = :dno_id 
 *    ORDER BY year DESC, voltage_level
 * 
 * 2. "HLZF Time Windows"
 *    SELECT year, voltage_level, winter, fruehling, sommer, herbst
 *    FROM hlzf
 *    WHERE dno_id = :dno_id
 *    ORDER BY year DESC
 * 
 * 3. "Recent Crawl Jobs"
 *    SELECT id, data_type, year, status, error_message, created_at
 *    FROM crawl_jobs
 *    WHERE dno_id = :dno_id
 *    ORDER BY created_at DESC
 *    LIMIT 20
 * 
 * 4. "Data Sources"
 *    SELECT year, data_type, source_url, extracted_at, extraction_method
 *    FROM data_sources
 *    WHERE dno_id = :dno_id
 *    ORDER BY year DESC
 * 
 * 5. "Price Trend (Last 5 Years)"
 *    SELECT year, voltage_level, arbeit, leistung
 *    FROM netzentgelte
 *    WHERE dno_id = :dno_id AND year >= 2020
 *    ORDER BY voltage_level, year
 * 
 * ============================================================================
 * COMPONENTS TO USE
 * ============================================================================
 * - Monaco Editor or CodeMirror for SQL syntax highlighting
 * - Table for results display
 * - Card for quick table buttons
 * - Collapsible for saved queries and schema
 * - Button, Select for actions
 * - Badge for row counts
 * 
 * ============================================================================
 * LOCAL STORAGE
 * ============================================================================
 * - Saved queries per DNO: localStorage key `sql_queries_${dno_id}`
 * - Query history (last 10): localStorage key `sql_history_${dno_id}`
 * - Last query: localStorage key `sql_last_${dno_id}`
 */

import { useOutletContext } from "react-router-dom";
import type { DNODetailContext } from "./types";

export function SQLExplorer() {
    const { dno, numericId } = useOutletContext<DNODetailContext>();

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold">SQL Explorer</h1>
                    <p className="text-muted-foreground">
                        Query database tables for this DNO
                    </p>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span className="px-2 py-1 bg-muted rounded-md font-mono">
                        dno_id = {numericId}
                    </span>
                    <span className="text-xs">Auto-scoped</span>
                </div>
            </div>

            {/* TODO: Implement SQL explorer */}
            <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">
                <p className="text-lg font-medium mb-2">SQL Explorer</p>
                <p className="text-sm">
                    This page will provide a SQL query interface for exploring {dno.name}'s data.
                </p>
                <p className="text-sm mt-2">
                    See component file for detailed implementation plan.
                </p>
                <div className="mt-4 p-4 bg-muted/50 rounded-md text-left font-mono text-xs">
                    <pre>{`-- Example query
SELECT year, voltage_level, arbeit, leistung
FROM netzentgelte
WHERE dno_id = ${numericId}
ORDER BY year DESC`}</pre>
                </div>
            </div>
        </div>
    );
}
