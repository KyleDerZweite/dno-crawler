/**
 * Callback component for handling OIDC redirect.
 *
 * This component should be rendered at your redirect_uri path.
 *
 * Usage in router:
 *
 * ```tsx
 * import { AuthCallback } from './lib/auth/auth-callback';
 *
 * <Route path="/callback" element={<AuthCallback />} />
 * ```
 */

import { useEffect } from "react";
import { useAuth } from "react-oidc-context";
import { useNavigate } from "react-router-dom";

export function AuthCallback() {
    const auth = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        // Wait for auth to complete
        if (!auth.isLoading) {
            if (auth.isAuthenticated) {
                // Check for stored redirect path
                const redirectPath = sessionStorage.getItem("auth_redirect") || "/";
                sessionStorage.removeItem("auth_redirect");
                navigate(redirectPath, { replace: true });
            } else if (auth.error) {
                console.error("Auth error:", auth.error);
                navigate("/", { replace: true });
            }
        }
    }, [auth.isLoading, auth.isAuthenticated, auth.error, navigate]);

    return (
        <div className="flex items-center justify-center min-h-screen">
            <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4" />
                <p>Completing login...</p>
            </div>
        </div>
    );
}
