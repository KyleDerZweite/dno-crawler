import { useQuery } from "@tanstack/react-query";
import { api, type User } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Shield,
  Users,
  Database,
  Activity,
  Loader2,
  CheckCircle,
  XCircle,
  RefreshCw,
  MoreVertical,
} from "lucide-react";

export function AdminPage() {
  const { user } = useAuth();

  const { data: usersResponse, isLoading: usersLoading } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.admin.listUsers(),
    enabled: user?.role === "admin",
  });

  const { data: dashboardResponse, isLoading: statsLoading } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: api.admin.getDashboard,
    enabled: user?.role === "admin",
  });

  const stats = dashboardResponse?.data;
  const users = usersResponse?.data;

  if (user?.role !== "admin") {
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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Users}
          title="Total Users"
          value={stats?.users.total || 0}
          color="text-primary"
          bg="bg-primary/20"
          loading={statsLoading}
        />
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

      {/* Users Management */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                User Management
              </CardTitle>
              <CardDescription>Manage system users and roles</CardDescription>
            </div>
            <Button variant="outline" size="sm">
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {usersLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-4">
              {users?.map((u: User) => (
                <UserRow key={u.id} user={u} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ icon: Icon, title, value, color, bg, loading }: any) {
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

function UserRow({ user }: { user: User }) {
  return (
    <div className="flex items-center justify-between p-4 border border-border/50 rounded-lg hover:bg-accent/5 transition-colors">
      <div className="flex items-center gap-4">
        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center ${user.role === "admin"
              ? "bg-purple-500/10 text-purple-500"
              : "bg-blue-500/10 text-blue-500"
            }`}
        >
          {user.email.charAt(0).toUpperCase()}
        </div>
        <div>
          <p className="font-medium">{user.name || user.email}</p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{user.email}</span>
            <span>•</span>
            <span className="capitalize">{user.role}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {user.is_active ? (
          <span className="px-2 py-0.5 text-xs rounded-full bg-success/20 text-success flex items-center gap-1">
            <CheckCircle className="h-3 w-3" /> Active
          </span>
        ) : (
          <span className="px-2 py-0.5 text-xs rounded-full bg-destructive/20 text-destructive flex items-center gap-1">
            <XCircle className="h-3 w-3" /> Inactive
          </span>
        )}
        <Button variant="ghost" size="icon">
          <MoreVertical className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}