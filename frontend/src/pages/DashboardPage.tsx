import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Link } from "react-router-dom";
import {
  Database,
  Activity,
  TrendingUp,
  Clock,
  Loader2,
  Search
} from "lucide-react";
import { Button } from "@/components/ui/button";

export function DashboardPage() {
  const { user } = useAuth();

  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      // In a real app, you'd have a stats endpoint
      const dnos = await api.dnos.list();
      return {
        totalDnos: dnos.data.length,
        activeCrawls: 0,
        lastUpdated: new Date().toLocaleDateString(),
        dataPoints: dnos.data.reduce((acc, dno) => acc + (dno.data_points_count || 0), 0),
      };
    },
  });

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">
          Welcome back{user?.name ? `, ${user.name}` : ""}!
        </h1>
        <p className="text-muted-foreground mt-2">
          Here's an overview of your DNO Crawler instance
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={Database}
          title="Total DNOs"
          value={stats?.totalDnos || 0}
          subtitle="Distribution network operators"
          isLoading={isLoading}
        />
        <StatCard
          icon={TrendingUp}
          title="Data Points"
          value={stats?.dataPoints?.toLocaleString() || 0}
          subtitle="Netzentgelte records"
          isLoading={isLoading}
          accent
        />
        <StatCard
          icon={Activity}
          title="Active Crawls"
          value={stats?.activeCrawls || 0}
          subtitle="Running extraction jobs"
          isLoading={isLoading}
        />
        <StatCard
          icon={Clock}
          title="Last Updated"
          value={stats?.lastUpdated || "Never"}
          subtitle="Most recent data sync"
          isLoading={isLoading}
        />
      </div>

      {/* Quick Actions */}
      <Card className="p-6">
        <CardHeader className="p-0 pb-4">
          <CardTitle className="text-lg">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="p-0 flex flex-wrap gap-4">
          <Button asChild>
            <Link to="/search" className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Search DNOs
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/dnos" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              View DNOs
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/jobs">View Jobs</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/settings">Settings</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  icon: Icon,
  title,
  value,
  subtitle,
  isLoading,
  accent = false
}: {
  icon: React.ElementType
  title: string
  value: string | number
  subtitle?: string
  isLoading: boolean
  accent?: boolean
}) {
  return (
    <Card className={`p-6 ${accent ? 'bg-gradient-to-br from-primary/10 to-transparent' : ''}`}>
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl ${accent ? 'bg-primary/20' : 'bg-secondary'}`}>
          <Icon className={`h-6 w-6 ${accent ? 'text-primary' : 'text-muted-foreground'}`} />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          {isLoading ? (
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          ) : (
            <p className={`text-2xl font-bold ${accent ? 'text-primary' : 'text-foreground'}`}>
              {value}
            </p>
          )}
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
    </Card>
  )
}