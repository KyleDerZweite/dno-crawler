/**
 * Tools View - Placeholder for Future Tools & Calculators
 */

import { Wrench } from "lucide-react";

export function Tools() {
    return (
        <div className="flex flex-col items-center justify-center h-[400px] text-center animate-in fade-in">
            <Wrench className="h-16 w-16 text-muted-foreground/20 mb-4" />
            <h2 className="text-xl font-semibold">Tools & Calculators</h2>
            <p className="text-muted-foreground max-w-md mt-2">
                Future expansion: Netzentgelte calculators, form automation, and compliance checkers will appear here.
            </p>
        </div>
    );
}
