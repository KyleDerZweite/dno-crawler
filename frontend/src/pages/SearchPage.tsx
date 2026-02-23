import { PublicSearchPanel } from "@/components/PublicSearchPanel";

export default function SearchPage() {
    return (
        <div className="space-y-8 max-w-5xl mx-auto">
            <div className="text-center">
                <h1 className="text-3xl font-bold text-foreground">Search DNO Data</h1>
                <p className="text-muted-foreground mt-2">
                    Find network operator data by address or coordinates
                </p>
            </div>

            <PublicSearchPanel showImportLinkForSkeleton={true} />
        </div>
    );
}
