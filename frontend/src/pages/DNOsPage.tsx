import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type DNO } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Database,
  Plus,
  ExternalLink,
  Loader2,
  Search,
  Check,
  RefreshCw,
  Zap,
  Clock,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";

interface AddDNOForm {
  name: string;
  slug: string;
  region: string;
  website: string;
  description: string;
}

const initialFormState: AddDNOForm = {
  name: "",
  slug: "",
  region: "",
  website: "",
  description: "",
};

export function DNOsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [formData, setFormData] = useState<AddDNOForm>(initialFormState);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: dnosResponse, isLoading } = useQuery({
    queryKey: ["dnos"],
    queryFn: () => api.dnos.list(true),
  });

  const dnos = dnosResponse?.data;

  const createDNOMutation = useMutation({
    mutationFn: (data: AddDNOForm) =>
      api.dnos.create({
        name: data.name,
        slug: data.slug || undefined,
        region: data.region || undefined,
        website: data.website || undefined,
        description: data.description || undefined,
      }),
    onSuccess: (response) => {
      toast({
        title: "DNO created",
        description: `${response.data.name} has been added successfully`,
      });
      queryClient.invalidateQueries({ queryKey: ["dnos"] });
      setIsAddDialogOpen(false);
      setFormData(initialFormState);
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
        title: "Failed to create DNO",
        description: message,
      });
    },
  });

  const handleFormChange = (field: keyof AddDNOForm, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      toast({
        variant: "destructive",
        title: "Validation error",
        description: "Name is required",
      });
      return;
    }
    createDNOMutation.mutate(formData);
  };

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
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add DNO
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <form onSubmit={handleSubmit}>
              <DialogHeader>
                <DialogTitle>Add New DNO</DialogTitle>
                <DialogDescription>
                  Add a new Distribution Network Operator to the system.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">
                    Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    placeholder="e.g., Stadtwerke München"
                    value={formData.name}
                    onChange={(e) => handleFormChange("name", e.target.value)}
                    required
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="slug">
                    Slug <span className="text-muted-foreground text-xs">(optional)</span>
                  </Label>
                  <Input
                    id="slug"
                    placeholder="Auto-generated from name if empty"
                    value={formData.slug}
                    onChange={(e) => handleFormChange("slug", e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="region">Region</Label>
                  <Input
                    id="region"
                    placeholder="e.g., Bayern, Nordrhein-Westfalen"
                    value={formData.region}
                    onChange={(e) => handleFormChange("region", e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="website">Website</Label>
                  <Input
                    id="website"
                    type="url"
                    placeholder="https://example.com"
                    value={formData.website}
                    onChange={(e) => handleFormChange("website", e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    placeholder="Brief description..."
                    value={formData.description}
                    onChange={(e) => handleFormChange("description", e.target.value)}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAddDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createDNOMutation.isPending}>
                  {createDNOMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Create DNO"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
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

      {/* DNO List - show empty state for both errors and empty results */}
      {!isLoading && (
        <div className="space-y-4">
          {(!filteredDnos || filteredDnos.length === 0) ? (
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
                    : "No DNOs have been added yet. Click 'Add DNO' to get started."}
                </p>
              </Card>
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                Showing {filteredDnos.length} of {dnos?.length || 0} DNOs
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredDnos.map((dno) => (
                  <DNOCard
                    key={dno.id}
                    dno={dno}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function DNOCard({ dno }: { dno: DNO }) {
  // Stuck detection: crawling for > 1 hour
  const isStuck =
    dno.status === "crawling" &&
    dno.crawl_locked_at &&
    new Date().getTime() - new Date(dno.crawl_locked_at).getTime() > 3600 * 1000;

  const getStatusBadge = () => {
    if (isStuck) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
          <RefreshCw className="h-3 w-3" />
          Stuck
        </span>
      );
    }

    switch (dno.status) {
      case "crawled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
            <Check className="h-3 w-3" />
            Crawled
          </span>
        );
      case "crawling":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            Crawling
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
            Uncrawled
          </span>
        );
    }
  };

  return (
    <Card className="group relative overflow-hidden transition-all duration-200 hover:shadow-glow flex flex-col h-full">
      <Link to={`/dnos/${dno.id}`} className="p-6 flex-1 cursor-pointer hover:bg-muted/50 transition-colors">
        <div className="flex justify-between items-start mb-4">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          <div className="flex items-center gap-2">
            {getStatusBadge()}
            {dno.website && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  window.open(dno.website, '_blank');
                }}
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <h3 className="font-bold text-xl mb-1 truncate" title={dno.name}>{dno.name}</h3>
        {dno.region && (
          <p className="text-sm text-muted-foreground mb-4">{dno.region}</p>
        )}

        {/* Mini Stats */}
        <div className="grid grid-cols-2 gap-3 mt-auto">
          <div className="flex items-center gap-2 p-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <Zap className="h-4 w-4 text-blue-500" />
            <div>
              <p className="text-base font-bold text-blue-600 dark:text-blue-400">
                {dno.netzentgelte_count ?? 0}
              </p>
              <p className="text-[10px] text-muted-foreground leading-tight">Netzentgelte</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <Clock className="h-4 w-4 text-purple-500" />
            <div>
              <p className="text-base font-bold text-purple-600 dark:text-purple-400">
                {dno.hlzf_count ?? 0}
              </p>
              <p className="text-[10px] text-muted-foreground leading-tight">HLZF</p>
            </div>
          </div>
        </div>
      </Link>
    </Card>
  );
}