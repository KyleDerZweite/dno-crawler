/**
 * Shared types for DNO Detail views
 */

import type { DNO } from "@/types";

export interface DNODetailContext {
    dno: DNO;
    numericId: string;
    isAdmin: boolean;
}

