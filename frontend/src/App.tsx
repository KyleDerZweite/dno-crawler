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
      {/* OIDC Callback route */}
      <Route path="/callback" element={<AuthCallback />} />

      {/* Login redirect */}
      <Route path="/login" element={<LoginRedirect />} />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="dnos" element={<DNOsPage />} />
        <Route path="dnos/:id" element={<DNODetailPage />} />
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

      {/* Catch all - redirect to dashboard */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
