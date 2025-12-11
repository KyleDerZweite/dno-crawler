import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Shield,
  Database,
  Activity,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export function AdminPage() {
  const { isAdmin } = useAuth();

  const { data: dashboardResponse, isLoading: statsLoading } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: api.admin.getDashboard,
    enabled: isAdmin(),
  });

  const stats = dashboardResponse?.data;

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
      <div className="grid gap-4 md:grid-cols-3">
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
      </div>

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