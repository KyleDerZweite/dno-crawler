import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import {
  Shield,
  Database,
  Activity,
  ExternalLink,
  AlertTriangle,
  Zap,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export function AdminPage() {
  const { isAdmin } = useAuth();

  const { data: dashboardResponse, isLoading: statsLoading } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: api.admin.getDashboard,
    enabled: isAdmin(),
  });

  const { data: flaggedResponse, isLoading: flaggedLoading } = useQuery({
    queryKey: ["admin", "flagged"],
    queryFn: api.admin.getFlagged,
    enabled: isAdmin(),
  });

  const stats = dashboardResponse?.data;
  const flaggedItems = flaggedResponse?.data?.items || [];

  // Parse structured flag reason for display
  const parseFlagReason = (reason?: string | null) => {
    if (!reason) return null;

    const parts: { issue?: string; fields?: string; notes?: string } = {};
    reason.split(" | ").forEach(part => {
      if (part.startsWith("Issue: ")) parts.issue = part.replace("Issue: ", "");
      else if (part.startsWith("Fields: ")) parts.fields = part.replace("Fields: ", "");
      else if (part.startsWith("Notes: ")) parts.notes = part.replace("Notes: ", "");
    });

    return parts;
  };

  if (!isAdmin()) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md p-8 text-center">
          <Shield className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
          <p className="text-muted-foreground">
            You need administrator privileges to access this page.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <Card className="p-5">
        <CardTitle className="font-semibold flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          Admin Dashboard
        </CardTitle>
        <p className="text-muted-foreground text-sm mt-2">System administration and monitoring</p>
      </Card>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          icon={Database}
          title="Total DNOs"
          value={stats?.dnos.total || 0}
          color="text-warning"
          bg="bg-warning/20"
          loading={statsLoading}
        />
        <StatCard
          icon={Activity}
          title="Running Jobs"
          value={stats?.jobs.running || 0}
          color="text-success"
          bg="bg-success/20"
          loading={statsLoading}
        />
        <StatCard
          icon={Activity}
          title="Pending Jobs"
          value={stats?.jobs.pending || 0}
          color="text-secondary-foreground"
          bg="bg-secondary"
          loading={statsLoading}
        />
        <StatCard
          icon={AlertTriangle}
          title="Flagged Items"
          value={stats?.flagged?.total || 0}
          color="text-amber-500"
          bg="bg-amber-500/20"
          loading={statsLoading}
        />
      </div>

      {/* Flagged Items Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Flagged Items
            {stats?.flagged?.total ? (
              <Badge variant="secondary" className="ml-2 bg-amber-500/20 text-amber-600">
                {stats.flagged.total}
              </Badge>
            ) : null}
          </CardTitle>
          <CardDescription>Data records flagged for review</CardDescription>
        </CardHeader>
        <CardContent>
          {flaggedLoading ? (
            <p className="text-muted-foreground text-center py-8">Loading...</p>
          ) : flaggedItems.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No flagged items</p>
            </div>
          ) : (
            <div className="space-y-2">
              <TooltipProvider>
                {flaggedItems.map((item) => {
                  const parsed = parseFlagReason(item.flag_reason);
                  return (
                    <Tooltip key={`${item.type}-${item.id}`}>
                      <TooltipTrigger asChild>
                        <Link
                          to={`/dnos/${item.dno_id}`}
                          className="flex items-center justify-between p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${item.type === "netzentgelte" ? "bg-blue-500/10 text-blue-500" : "bg-purple-500/10 text-purple-500"}`}>
                              {item.type === "netzentgelte" ? <Zap className="h-4 w-4" /> : <Clock className="h-4 w-4" />}
                            </div>
                            <div>
                              <p className="font-medium text-sm">{item.dno_name}</p>
                              <p className="text-xs text-muted-foreground">
                                {item.type === "netzentgelte" ? "Netzentgelte" : "HLZF"} • {item.voltage_level} • {item.year}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {parsed?.issue && (
                              <Badge variant="outline" className="text-xs border-amber-500/50 text-amber-600">
                                {parsed.issue}
                              </Badge>
                            )}
                            {item.flagged_at && (
                              <span className="text-xs text-muted-foreground">
                                {new Date(item.flagged_at).toLocaleDateString("de-DE")}
                              </span>
                            )}
                          </div>
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <div className="space-y-1.5">
                          <div className="font-medium text-amber-400">⚠ Flag Details</div>
                          {parsed?.issue && (
                            <div className="text-xs">
                              <span className="text-muted-foreground">Issue:</span>{" "}
                              <span className="font-medium">{parsed.issue}</span>
                            </div>
                          )}
                          {parsed?.fields && (
                            <div className="text-xs">
                              <span className="text-muted-foreground">Fields:</span>{" "}
                              <span>{parsed.fields}</span>
                            </div>
                          )}
                          {parsed?.notes && (
                            <div className="text-xs">
                              <span className="text-muted-foreground">Notes:</span>{" "}
                              <span className="italic">{parsed.notes}</span>
                            </div>
                          )}
                          {!parsed?.issue && item.flag_reason && (
                            <div className="text-xs opacity-80">{item.flag_reason}</div>
                          )}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </TooltipProvider>
            </div>
          )}
        </CardContent>
      </Card>

      {/* User Management Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            User Management
          </CardTitle>
          <CardDescription>Users are managed through Zitadel</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 border border-border/50 rounded-lg bg-muted/20">
            <div>
              <p className="font-medium">Zitadel Console</p>
              <p className="text-sm text-muted-foreground">
                Manage users, roles, and authentication settings in the centralized identity provider.
              </p>
            </div>
            <Button variant="outline" asChild>
              <a
                href={import.meta.env.VITE_ZITADEL_AUTHORITY}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="mr-2 h-4 w-4" />
                Open Zitadel
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ icon: Icon, title, value, color, bg, loading }: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  value: number;
  color: string;
  bg: string;
  loading: boolean;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-full ${bg}`}>
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
        <div>
          <div className="text-2xl font-bold">
            {loading ? "..." : value}
          </div>
          <p className="text-muted-foreground text-sm">{title}</p>
        </div>
      </div>
    </Card>
  )
}