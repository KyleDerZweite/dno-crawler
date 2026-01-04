import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/use-auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type DNO, type VNBSuggestion } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  Zap,
  Clock,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";

interface AddDNOForm {
  name: string;
  slug: string;
  region: string;
  website: string;
  description: string;
  vnb_id: string;  // VNB Digital ID for validation
  phone: string;
  email: string;
  contact_address: string;
}

const initialFormState: AddDNOForm = {
  name: "",
  slug: "",
  region: "",
  website: "",
  description: "",
  vnb_id: "",
  phone: "",
  email: "",
  contact_address: "",
};

export function DNOsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [formData, setFormData] = useState<AddDNOForm>(initialFormState);

  // Pagination state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);

  // VNB Autocomplete state
  const [vnbSuggestions, setVnbSuggestions] = useState<VNBSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSearchingVnb, setIsSearchingVnb] = useState(false);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { isAdmin } = useAuth();

  const { data: dnosResponse, isLoading } = useQuery({
    queryKey: ["dnos", page, perPage],
    queryFn: () => api.dnos.list({ include_stats: true, page, per_page: perPage }),
    refetchOnMount: "always",
    refetchInterval: 5000, // Poll every 5 seconds for live status updates
  });

  const dnos = dnosResponse?.data;
  const meta = dnosResponse?.meta;

  const createDNOMutation = useMutation({
    mutationFn: (data: AddDNOForm) =>
      api.dnos.create({
        name: data.name,
        slug: data.slug || undefined,
        region: data.region || undefined,
        website: data.website || undefined,
        description: data.description || undefined,
        vnb_id: data.vnb_id || undefined,
        phone: data.phone || undefined,
        email: data.email || undefined,
        contact_address: data.contact_address || undefined,
      }),
    onSuccess: (response) => {
      toast({
        title: "DNO created",
        description: `${response.data.name} has been added successfully`,
      });
      queryClient.invalidateQueries({ queryKey: ["dnos"] });
      setIsAddDialogOpen(false);
      setFormData(initialFormState);
      setVnbSuggestions([]);
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

  // Debounced VNB search (1 second delay per user request)
  const searchVnb = useCallback(async (query: string) => {
    if (query.length < 2) {
      setVnbSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    setIsSearchingVnb(true);
    try {
      const response = await api.dnos.searchVnb(query);
      setVnbSuggestions(response.data.suggestions);
      setShowSuggestions(response.data.suggestions.length > 0);
    } catch (error) {
      console.error("VNB search failed:", error);
      setVnbSuggestions([]);
    } finally {
      setIsSearchingVnb(false);
    }
  }, []);

  // Handle name input with debounced VNB search
  const handleNameChange = (value: string) => {
    setFormData((prev) => ({ ...prev, name: value, vnb_id: "" }));

    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    // Set new timeout (1 second debounce)
    searchTimeoutRef.current = setTimeout(() => {
      searchVnb(value);
    }, 1000);
  };

  // Handle VNB suggestion selection
  const handleSelectVnb = async (suggestion: VNBSuggestion) => {
    setShowSuggestions(false);
    setFormData((prev) => ({
      ...prev,
      name: suggestion.name,
      vnb_id: suggestion.vnb_id,
    }));

    // Fetch extended details for auto-fill
    try {
      const details = await api.dnos.getVnbDetails(suggestion.vnb_id);
      setFormData((prev) => ({
        ...prev,
        website: details.data.website || prev.website,
        phone: details.data.phone || prev.phone,
        email: details.data.email || prev.email,
        contact_address: details.data.address || prev.contact_address,
      }));
      toast({
        title: "VNB details loaded",
        description: "Form has been auto-filled with VNB data.",
      });
    } catch (error) {
      console.error("Failed to fetch VNB details:", error);
    }
  };

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, []);

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
        {/* TODO was: Future enhancement - validate DNO against VNB Digital API - NOW IMPLEMENTED */}
        {isAdmin() && (
          <Dialog open={isAddDialogOpen} onOpenChange={(open) => {
            setIsAddDialogOpen(open);
            if (!open) {
              setFormData(initialFormState);
              setVnbSuggestions([]);
              setShowSuggestions(false);
            }
          }}>
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
                    Add a new Distribution Network Operator. Start typing to search VNB Digital.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {/* Name with VNB Autocomplete */}
                  <div className="grid gap-2 relative" ref={suggestionsRef}>
                    <Label htmlFor="name">
                      Name <span className="text-destructive">*</span>
                    </Label>
                    <div className="relative">
                      <Input
                        id="name"
                        placeholder="e.g., Stadtwerke München"
                        value={formData.name}
                        onChange={(e) => handleNameChange(e.target.value)}
                        required
                        autoComplete="off"
                      />
                      {isSearchingVnb && (
                        <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
                      )}
                    </div>
                    {formData.vnb_id && (
                      <p className="text-xs text-green-600 flex items-center gap-1">
                        <Check className="h-3 w-3" />
                        Linked to VNB: {formData.vnb_id}
                      </p>
                    )}

                    {/* Suggestions Dropdown */}
                    {showSuggestions && vnbSuggestions.length > 0 && (
                      <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-popover border rounded-md shadow-lg max-h-48 overflow-y-auto">
                        {vnbSuggestions.map((suggestion) => (
                          <button
                            key={suggestion.vnb_id}
                            type="button"
                            className="w-full px-3 py-2 text-left hover:bg-accent flex items-center justify-between gap-2"
                            onClick={() => handleSelectVnb(suggestion)}
                          >
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">{suggestion.name}</p>
                              {suggestion.subtitle && (
                                <p className="text-xs text-muted-foreground truncate">
                                  {suggestion.subtitle}
                                </p>
                              )}
                            </div>
                            {suggestion.exists && (
                              <span className="flex items-center gap-1 text-xs text-amber-600 flex-shrink-0">
                                <AlertTriangle className="h-3 w-3" />
                                Exists
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
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
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="phone">Phone</Label>
                      <Input
                        id="phone"
                        placeholder="+49..."
                        value={formData.phone}
                        onChange={(e) => handleFormChange("phone", e.target.value)}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="contact@dno.de"
                        value={formData.email}
                        onChange={(e) => handleFormChange("email", e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="contact_address">Address</Label>
                    <Input
                      id="contact_address"
                      placeholder="Musterstraße 1, 12345 Stadt"
                      value={formData.contact_address}
                      onChange={(e) => handleFormChange("contact_address", e.target.value)}
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
        )}
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
              {/* Pagination Header */}
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {((page - 1) * perPage) + 1}-{Math.min(page * perPage, meta?.total || 0)} of {meta?.total || 0} DNOs
                  {searchTerm && ` (${filteredDnos.length} matching filter)`}
                </p>
                <div className="flex items-center gap-4">
                  {/* Page Size Selector */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Per page:</span>
                    <Select
                      value={String(perPage)}
                      onValueChange={(value) => {
                        setPerPage(Number(value));
                        setPage(1); // Reset to first page on size change
                      }}
                    >
                      <SelectTrigger className="w-20 h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="25">25</SelectItem>
                        <SelectItem value="50">50</SelectItem>
                        <SelectItem value="100">100</SelectItem>
                        <SelectItem value="250">250</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {/* Page Navigation */}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm text-muted-foreground min-w-[80px] text-center">
                      Page {page} of {meta?.total_pages || 1}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(meta?.total_pages || 1, p + 1))}
                      disabled={page >= (meta?.total_pages || 1)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredDnos.map((dno) => (
                  <DNOCard
                    key={dno.id}
                    dno={dno}
                  />
                ))}
              </div>
              {/* Bottom Pagination (for long lists) */}
              {(meta?.total_pages || 1) > 1 && (
                <div className="flex justify-center pt-4">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground px-4">
                      Page {page} of {meta?.total_pages || 1}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(meta?.total_pages || 1, p + 1))}
                      disabled={page >= (meta?.total_pages || 1)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function DNOCard({ dno }: { dno: DNO }) {
  const getStatusBadge = () => {
    switch (dno.status) {
      case "crawled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
            <Check className="h-3 w-3" />
            Crawled
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            Running
          </span>
        );
      case "pending":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
            <Clock className="h-3 w-3" />
            Pending
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
        <div className="grid grid-cols-3 gap-2 mt-auto">
          <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <Zap className="h-4 w-4 text-blue-500" />
            <span className="text-base font-bold text-blue-600 dark:text-blue-400">
              {dno.netzentgelte_count ?? 0}
            </span>
          </div>
          <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <Clock className="h-4 w-4 text-purple-500" />
            <span className="text-base font-bold text-purple-600 dark:text-purple-400">
              {dno.hlzf_count ?? 0}
            </span>
          </div>
          <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-green-500/10 border border-green-500/20">
            <span className="text-base font-bold text-green-600 dark:text-green-400">
              {Math.min(Math.round(((dno.netzentgelte_count ?? 0) + (dno.hlzf_count ?? 0)) / 50 * 100), 100)}%
            </span>
          </div>
        </div>
      </Link>
    </Card>
  );
}