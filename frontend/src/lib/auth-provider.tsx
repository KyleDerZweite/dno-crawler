import { AuthProvider as OidcAuthProvider } from "react-oidc-context";
import { authConfig } from "./auth-config";

interface AuthProviderProps {
    children: React.ReactNode;
}

/**
 * AuthProvider wraps the application with OIDC authentication context.
 *
 * Usage in main.tsx:
 *
 * ```tsx
 * import { AuthProvider } from './lib/auth/auth-provider';
 *
 * ReactDOM.createRoot(document.getElementById('root')!).render(
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 * );
 * ```
 */
export function AuthProvider({ children }: AuthProviderProps) {
    const authority = import.meta.env.VITE_ZITADEL_AUTHORITY;
    const isAuthEnabled = authority && authority !== "https://auth.example.com";

    if (!isAuthEnabled) {
        return <>{children}</>;
    }

    const onSigninCallback = () => {
        // Remove the code and state from URL after successful login
        window.history.replaceState({}, document.title, window.location.pathname);
    };

    return (
        <OidcAuthProvider {...authConfig} onSigninCallback={onSigninCallback}>
            {children}
        </OidcAuthProvider>
    );
}
