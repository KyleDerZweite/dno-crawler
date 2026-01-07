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
  Search,
  ArrowRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function DashboardPage() {
  const { user } = useAuth();

  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const response = await api.dnos.getStats();
      return {
        totalDnos: response.data.total_dnos,
        activeCrawls: response.data.active_crawls,
        lastUpdated: new Date().toLocaleDateString(),
        dataPoints: response.data.total_data_points,
      };
    },
  });

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-2xl font-semibold text-foreground tracking-tight">
          Welcome back{user?.name ? `, ${user.name}` : ""}
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Here's an overview of your DNO Crawler instance
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
          subtitle="Total records"
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
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-medium">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild className="gap-2">
            <Link to="/search">
              <Search className="h-4 w-4" />
              Search DNOs
              <ArrowRight className="h-3.5 w-3.5 ml-1 opacity-60" />
            </Link>
          </Button>
          <Button variant="secondary" asChild className="gap-2">
            <Link to="/dnos">
              <Database className="h-4 w-4" />
              View DNOs
            </Link>
          </Button>
          <Button variant="secondary" asChild>
            <Link to="/jobs">View Jobs</Link>
          </Button>
          <Button variant="ghost" asChild className="text-muted-foreground">
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
    <Card className={cn(
      "p-6 transition-all duration-200 hover:border-emerald-400/30",
      accent && "bg-gradient-to-br from-primary/10 to-transparent"
    )}>
      <div className="flex items-center gap-4">
        <div className={cn(
          "p-3 rounded-lg",
          accent ? "bg-primary/15" : "bg-secondary"
        )}>
          <Icon className={cn(
            "h-5 w-5",
            accent ? "text-primary" : "text-muted-foreground"
          )} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-muted-foreground font-medium">{title}</p>
          {isLoading ? (
            <Skeleton className="h-7 w-20 my-1" />
          ) : (
            <p className={cn(
              "text-2xl font-semibold tracking-tight",
              accent ? "text-primary" : "text-foreground"
            )}>
              {value}
            </p>
          )}
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
    </Card>
  )
}