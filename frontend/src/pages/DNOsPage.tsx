import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type DNO } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
} from "@/components/ui/card";
import {
  Database,
  Plus,
  ExternalLink,
  RefreshCw,
  Loader2,
  Search,
  Check,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";

export function DNOsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: dnosResponse, isLoading, error } = useQuery({
    queryKey: ["dnos"],
    queryFn: () => api.dnos.list(true),
  });

  const dnos = dnosResponse?.data;

  const triggerCrawlMutation = useMutation({
    mutationFn: (dnoId: string) => api.dnos.triggerCrawl(dnoId, { year: new Date().getFullYear() }),
    onSuccess: () => {
      toast({
        title: "Crawl triggered",
        description: "The crawler job has been queued",
      });
      queryClient.invalidateQueries({ queryKey: ["dnos"] });
    },
    onError: (error: unknown) => {
      const message =
        error instanceof AxiosError
          ? error.response?.data?.detail ?? error.message
          : error instanceof Error
            ? error.message
            : "Unknown error";

      toast({
        variant: "destructive",
        title: "Failed to trigger crawl",
        description: message,
      });
    },
  });

  const filteredDnos = dnos?.filter(
    (dno) =>
      dno.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      dno.region?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Distribution Network Operators
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage data sources and trigger crawls
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Add DNO
        </Button>
      </div>

      {/* Search */}
      <Card className="p-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by name, region..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
      </Card>

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-error/10 border border-error/20 rounded-xl p-6">
          <p className="text-error text-center">
            Error loading DNOs: {(error as Error).message}
          </p>
        </div>
      )}

      {/* DNO List */}
      {filteredDnos && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Showing {filteredDnos.length} of {dnos?.length || 0} DNOs
          </p>

          {filteredDnos.length === 0 ? (
            <div className="text-center py-16">
              <Card className="rounded-2xl p-8 max-w-md mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4 shadow-glow">
                  <Database className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-2">
                  No DNOs found
                </h3>
                <p className="text-muted-foreground">
                  {searchTerm
                    ? "No DNOs match your search terms."
                    : "No DNOs configured yet."}
                </p>
              </Card>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredDnos.map((dno) => (
                <DNOCard
                  key={dno.id}
                  dno={dno}
                  onTriggerCrawl={() => triggerCrawlMutation.mutate(dno.id)}
                  isCrawling={triggerCrawlMutation.isPending}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DNOCard({
  dno,
  onTriggerCrawl,
  isCrawling,
}: {
  dno: DNO;
  onTriggerCrawl: () => void;
  isCrawling: boolean;
}) {
  return (
    <Card className="group relative overflow-hidden transition-all duration-200 hover:shadow-glow flex flex-col h-full">
      <div className="p-6 flex-1">
        <div className="flex justify-between items-start mb-4">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          {dno.website && (
            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" asChild>
              <a href={dno.website} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
        </div>
        
        <h3 className="font-bold text-lg mb-1 truncate" title={dno.name}>{dno.name}</h3>
        {dno.region && (
          <p className="text-sm text-muted-foreground mb-4">{dno.region}</p>
        )}
        
        <div className="space-y-2 mt-4">
           <div className="flex items-center justify-between text-sm">
             <span className="text-muted-foreground">Status</span>
             <span className={cn("flex items-center gap-1.5 font-medium", true ? "text-success" : "text-muted-foreground")}>
               <Check className="h-3.5 w-3.5" /> Active
             </span>
           </div>
           {/* Placeholder for record count if API provided it */}
           {/* <div className="flex items-center justify-between text-sm">
             <span className="text-muted-foreground">Records</span>
             <span className="font-medium">{dno.netzentgelte_count || 0}</span>
           </div> */}
        </div>
      </div>

      <div className="p-4 border-t border-border bg-secondary/30">
        <Button 
          variant="outline" 
          className="w-full" 
          onClick={onTriggerCrawl}
          disabled={isCrawling}
        >
          {isCrawling ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Crawling...
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Trigger Crawl
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}