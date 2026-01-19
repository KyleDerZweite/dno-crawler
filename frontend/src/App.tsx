import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth, AuthCallback, ProtectedRoute } from "./lib";
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

  // Auto-redirect to Zitadel login
  login();
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
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="dnos" element={<DNOsPage />} />
        {/* DNO Detail with nested routes */}
        <Route path="dnos/:id" element={<DNODetailPage />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="data" element={<DataExplorer />} />
          <Route path="analysis" element={<Analysis />} />
          <Route path="files" element={<SourceFiles />} />
          <Route path="jobs" element={<JobHistory />} />
          <Route path="tools" element={<Tools />} />
          <Route path="technical" element={<Technical />} />
          <Route path="sql" element={<SQLExplorer />} />
        </Route>
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:id" element={<JobDetailsPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="settings" element={<SettingsPage />} />
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
