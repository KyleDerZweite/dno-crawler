/**
 * Shared types for DNO Detail views
 */

import type { DNO } from "@/lib/api";

export interface DNODetailContext {
    dno: DNO;
    numericId: string;
    isAdmin: boolean;
}

