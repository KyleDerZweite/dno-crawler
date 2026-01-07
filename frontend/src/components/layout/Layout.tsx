import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/use-auth"
import { cn } from "@/lib/utils"
import {
  Activity,
  ChevronRight,
  Database,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Settings,
  Shield,
  X,
} from "lucide-react"
import { useState, useEffect } from "react"
import { Link, Outlet, useLocation } from "react-router-dom"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Search", href: "/search", icon: Search },
  { name: "DNOs", href: "/dnos", icon: Database },
  { name: "Jobs", href: "/jobs", icon: Activity },
]

const adminNavigation = [
  { name: "Admin", href: "/admin", icon: Shield },
]

export function Layout() {
  const { user, logout, isAdmin, avatar, roles } = useAuth()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarExpanded, setSidebarExpanded] = useState(true)
  const [isManualToggle, setIsManualToggle] = useState(false)

  const allNavigation = isAdmin()
    ? [...navigation, ...adminNavigation]
    : navigation

  // Responsive sidebar: auto-collapse on medium screens, expand on large
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth
      // Only auto-adjust if user hasn't manually toggled
      if (!isManualToggle) {
        if (width >= 1280) {
          // xl and above: expanded
          setSidebarExpanded(true)
        } else if (width >= 1024) {
          // lg (1024-1279): collapsed
          setSidebarExpanded(false)
        }
      }
    }

    // Initial check
    handleResize()

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [isManualToggle])

  // Reset manual toggle when crossing breakpoints significantly
  useEffect(() => {
    const handleBreakpointReset = () => {
      const width = window.innerWidth
      // Reset manual toggle if we go to mobile or back to xl+
      if (width < 1024 || width >= 1280) {
        setIsManualToggle(false)
      }
    }

    window.addEventListener('resize', handleBreakpointReset)
    return () => window.removeEventListener('resize', handleBreakpointReset)
  }, [])

  // Derive page title for document and header
  const path = location.pathname;
  const pageMap: Record<string, string> = {
    "/dashboard": "Dashboard",
    "/search": "Search",
    "/dnos": "DNOs",
    "/jobs": "Jobs",
    "/admin": "Admin",
    "/settings": "Settings",
  };
  let page = pageMap[path];
  if (!page) {
    if (path.startsWith("/dnos")) page = "DNOs";
    if (path.startsWith("/jobs")) page = "Jobs";
    if (path.startsWith("/admin")) page = "Admin";
    if (path === "/") page = "Dashboard";
  }
  useEffect(() => {
    const title = `DNO-Crawler${page ? ` | ${page}` : ""}`;
    document.title = title;
  }, [path, page]);

  return (
    <div className="min-h-screen bg-background font-sans text-foreground">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col bg-card border-r border-border transition-all duration-300 ease-in-out lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          sidebarExpanded ? "w-64" : "w-16"
        )}
      >
        {/* Brand Header */}
        <div className={cn(
          "flex h-16 items-center border-b border-border px-4",
          sidebarExpanded ? "justify-between" : "justify-center"
        )}>
          <Link to="/dashboard" className="flex items-center gap-3 group">
            <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg bg-emerald-400/10 group-hover:bg-emerald-400/20 transition-colors">
              <svg className="h-5 w-5" viewBox="0 0 32 32" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 8v6" />
                <path d="M16 14L10 19" />
                <path d="M16 14L22 19" />
                <circle cx="16" cy="14" r="2.5" fill="#34d399" stroke="none" />
                <circle cx="10" cy="19" r="1.5" fill="#34d399" stroke="none" />
                <circle cx="22" cy="19" r="1.5" fill="#34d399" stroke="none" />
                <path d="M12 23h8" strokeOpacity="0.8" />
                <path d="M16 19v3" />
                <path d="M14 20l2 2 2-2" fill="none" />
                <path d="M21 7l-1 3h2l-2 3" stroke="#5ae3b1" strokeWidth="1.5" fill="none" />
              </svg>
            </div>
            {sidebarExpanded && (
              <span className="text-base font-semibold text-foreground tracking-tight">
                DNO-Crawler
              </span>
            )}
          </Link>
          
          {/* Collapse button - desktop only */}
          <button
            onClick={() => {
              setIsManualToggle(true)
              setSidebarExpanded(!sidebarExpanded)
            }}
            className={cn(
              "hidden lg:flex items-center justify-center w-6 h-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors",
              !sidebarExpanded && "absolute -right-3 top-5 bg-card border border-border shadow-sm"
            )}
          >
            <ChevronRight className={cn(
              "h-4 w-4 transition-transform duration-200",
              sidebarExpanded && "rotate-180"
            )} />
          </button>
          
          {/* Mobile close button */}
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden hover:bg-secondary text-muted-foreground hover:text-foreground h-8 w-8"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Navigation Menu */}
        <nav className="flex-1 overflow-y-auto px-2 pt-4">
          <div className="flex flex-col gap-1">
            <TooltipProvider delayDuration={0}>
              {allNavigation.map((item) => {
                const isActive =
                  location.pathname === item.href ||
                  location.pathname.startsWith(item.href + "/")
                
                const linkContent = (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={cn(
                      "flex items-center rounded-md transition-colors px-3 py-2.5 relative",
                      sidebarExpanded ? "justify-start gap-3" : "justify-center",
                      isActive
                        ? "bg-secondary text-foreground font-medium"
                        : "text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
                    )}
                    onClick={() => setSidebarOpen(false)}
                  >
                    {isActive && (
                      <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-primary/40 rounded-full" />
                    )}
                    <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                      <item.icon className="h-4 w-4" />
                    </span>
                    {sidebarExpanded && <span className="text-sm">{item.name}</span>}
                  </Link>
                )
                
                if (!sidebarExpanded) {
                  return (
                    <Tooltip key={item.name}>
                      <TooltipTrigger asChild>
                        {linkContent}
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        {item.name}
                      </TooltipContent>
                    </Tooltip>
                  )
                }
                
                return linkContent
              })}
            </TooltipProvider>
          </div>
          
          {/* Settings link - separate section */}
          <div className="mt-6 pt-4 border-t border-border">
            <TooltipProvider delayDuration={0}>
              {(() => {
                const isSettingsActive = location.pathname === "/settings" || location.pathname.startsWith("/settings/")
                const settingsLink = (
                  <Link
                    to="/settings"
                    className={cn(
                      "flex items-center rounded-md transition-colors px-3 py-2.5 relative",
                      sidebarExpanded ? "justify-start gap-3" : "justify-center",
                      isSettingsActive
                        ? "bg-secondary text-foreground font-medium"
                        : "text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
                    )}
                    onClick={() => setSidebarOpen(false)}
                  >
                    {isSettingsActive && (
                      <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-primary/40 rounded-full" />
                    )}
                    <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                      <Settings className="h-4 w-4" />
                    </span>
                    {sidebarExpanded && <span className="text-sm">Settings</span>}
                  </Link>
                )
                
                if (!sidebarExpanded) {
                  return (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        {settingsLink}
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        Settings
                      </TooltipContent>
                    </Tooltip>
                  )
                }
                
                return settingsLink
              })()}
            </TooltipProvider>
          </div>
        </nav>

        {/* Gradient fade at bottom of nav */}
        <div className="sticky bottom-[72px] left-0 right-0 h-6 pointer-events-none bg-gradient-to-t from-card to-transparent" />

        {/* User Profile */}
        <div className={cn(
          "border-t border-border p-3",
          !sidebarExpanded && "flex flex-col items-center"
        )}>
          {!user && (
            <div className="flex items-center justify-center py-2">
              <Link to="/login" className="text-sm text-primary hover:underline font-medium">
                Sign in
              </Link>
            </div>
          )}
          {user && (
            <TooltipProvider delayDuration={0}>
              {sidebarExpanded ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-lg bg-primary/10 p-[1px] overflow-hidden flex-shrink-0">
                      {avatar ? (
                        <img src={avatar} alt={user?.name || 'User'} className="h-full w-full rounded-lg object-cover" />
                      ) : (
                        <div className="h-full w-full rounded-lg bg-secondary flex items-center justify-center">
                          <span className="text-sm font-semibold text-primary">
                            {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "U"}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col overflow-hidden min-w-0">
                      <span className="text-sm font-medium text-foreground truncate">
                        {user?.name || user?.email}
                      </span>
                      <span className="text-xs text-muted-foreground truncate">
                        {roles.join(', ') || 'Member'}
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    className="w-full justify-start text-muted-foreground hover:text-red-400 hover:bg-red-500/10 h-9 text-sm font-medium"
                    onClick={logout}
                  >
                    <LogOut className="h-4 w-4 mr-2" />
                    Sign Out
                  </Button>
                </div>
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={logout}
                      className="flex items-center justify-center w-full rounded-md px-3 py-2.5 text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-colors"
                    >
                      <LogOut className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="font-medium">
                    Sign Out
                  </TooltipContent>
                </Tooltip>
              )}
            </TooltipProvider>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className={cn(
        "min-h-screen flex flex-col transition-all duration-300",
        sidebarExpanded ? "lg:pl-64" : "lg:pl-16"
      )}>
        {/* Mobile Header */}
        <header className="lg:hidden sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border bg-card px-4">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <span className="font-semibold">DNO-Crawler{page ? ` | ${page}` : ''}</span>
        </header>

        {/* Main Content */}
        <main className="flex-1 min-h-screen">
          <div className="container mx-auto p-6 md:p-8 max-w-7xl animate-in fade-in duration-300">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}