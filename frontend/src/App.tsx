import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth, AuthCallback, ProtectedRoute } from "./lib";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/layout/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { DNOsPage } from "./pages/DNOsPage";
import { DNODetailPage } from "./pages/DNODetailPage";
import { AdminPage } from "./pages/AdminPage";
import { SettingsPage } from "./pages/SettingsPage";
import { JobsPage } from "./pages/JobsPage";
import { JobDetailsPage } from "./pages/JobDetailsPage";
import SearchPage from "./pages/SearchPage";
import LandingPage from "./pages/LandingPage";
import LogoutPage from "./pages/LogoutPage";
import {
  Overview,
  DataExplorer,
  Analysis,
  SourceFiles,
  JobHistory,
  Tools,
  Technical,
  SQLExplorer,
} from "./features/dno-detail/views";

function LoginRedirect() {
  const { isAuthenticated, isLoading, login } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      login();
    }
  }, [isLoading, isAuthenticated, login]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-lg">Redirecting to login...</div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      {/* Public landing page */}
      <Route path="/" element={<LandingPage />} />

      {/* OIDC Callback route */}
      <Route path="/callback" element={<AuthCallback />} />

      {/* Login redirect */}
      <Route path="/login" element={<LoginRedirect />} />

      {/* Logout confirmation page */}
      <Route path="/logout" element={<LogoutPage />} />

      {/* Protected routes with sidebar layout */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="dashboard" element={<ErrorBoundary inline><DashboardPage /></ErrorBoundary>} />
        <Route path="search" element={<ErrorBoundary inline><SearchPage /></ErrorBoundary>} />
        <Route path="dnos" element={<ErrorBoundary inline><DNOsPage /></ErrorBoundary>} />
        {/* DNO Detail with nested routes */}
        <Route path="dnos/:id" element={<ErrorBoundary inline><DNODetailPage /></ErrorBoundary>}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<ErrorBoundary inline><Overview /></ErrorBoundary>} />
          <Route path="data" element={<ErrorBoundary inline><DataExplorer /></ErrorBoundary>} />
          <Route path="analysis" element={<ErrorBoundary inline><Analysis /></ErrorBoundary>} />
          <Route path="files" element={<ErrorBoundary inline><SourceFiles /></ErrorBoundary>} />
          <Route path="jobs" element={<ErrorBoundary inline><JobHistory /></ErrorBoundary>} />
          <Route path="tools" element={<ErrorBoundary inline><Tools /></ErrorBoundary>} />
          <Route path="technical" element={<ErrorBoundary inline><Technical /></ErrorBoundary>} />
          <Route path="sql" element={<ErrorBoundary inline><SQLExplorer /></ErrorBoundary>} />
        </Route>
        <Route path="jobs" element={<ErrorBoundary inline><JobsPage /></ErrorBoundary>} />
        <Route path="jobs/:id" element={<ErrorBoundary inline><JobDetailsPage /></ErrorBoundary>} />
        <Route path="admin" element={<ErrorBoundary inline><AdminPage /></ErrorBoundary>} />
        <Route path="settings" element={<ErrorBoundary inline><SettingsPage /></ErrorBoundary>} />
      </Route>

      {/* Unauthorized page */}
      <Route
        path="/unauthorized"
        element={
          <div className="flex h-screen items-center justify-center">
            <div className="text-center">
              <h1 className="text-2xl font-bold mb-2">Access Denied</h1>
              <p className="text-muted-foreground">You don't have permission to access this page.</p>
            </div>
          </div>
        }
      />

      {/* Catch all - redirect to landing */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
