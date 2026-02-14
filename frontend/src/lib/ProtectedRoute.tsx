import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./use-auth";

interface ProtectedRouteProps {
    children: React.ReactNode;
    requiredRole?: string;
}

/**
 * ProtectedRoute ensures only authenticated users can access the wrapped content.
 *
 * Usage in router:
 *
 * ```tsx
 * <Route
 *   path="/dashboard"
 *   element={
 *     <ProtectedRoute>
 *       <Dashboard />
 *     </ProtectedRoute>
 *   }
 * />
 *
 * // With role requirement:
 * <Route
 *   path="/admin"
 *   element={
 *     <ProtectedRoute requiredRole="ADMIN">
 *       <AdminPanel />
 *     </ProtectedRoute>
 *   }
 * />
 * ```
 */
export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
    const { isAuthenticated, isLoading, hasRole, login } = useAuth();
    const location = useLocation();

    // Show loading state while checking auth
    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen" role="status" aria-busy="true">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
                <span className="sr-only">Loading authentication status...</span>
            </div>
        );
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        // Store the intended destination for redirect after login
        sessionStorage.setItem("auth_redirect", location.pathname);
        login();
        return null;
    }

    // Check role if required
    if (requiredRole && !hasRole(requiredRole)) {
        return <Navigate to="/unauthorized" replace />;
    }

    return <>{children}</>;
}
