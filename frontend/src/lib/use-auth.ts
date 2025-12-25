import { useAuth as useOidcAuth } from "react-oidc-context";

/**
 * Custom auth hook with Kylehub-specific helpers.
 *
 * Provides:
 * - user: The authenticated user's profile
 * - avatar: User's profile picture URL from Zitadel
 * - isAuthenticated: Boolean indicating auth state
 * - isLoading: Boolean indicating loading state
 * - login: Function to trigger login redirect
 * - logout: Function to trigger logout
 * - openSettings: Function to open Zitadel account settings
 * - accessToken: The current access token (for API calls)
 * - hasRole: Function to check if user has a specific role
 */
export function useAuth() {
    const authority = import.meta.env.VITE_ZITADEL_AUTHORITY;
    const isAuthEnabled = authority && authority !== "https://auth.example.com";

    // Handle Mock Admin if auth is disabled or pointing to example.com
    if (!isAuthEnabled) {
        return {
            user: {
                sub: "mock-admin-id",
                email: "admin@dno-crawler.local",
                name: "Mock Admin",
                preferred_username: "admin"
            },
            avatar: undefined,
            accessToken: "mock-token",
            isAuthenticated: true,
            isLoading: false,
            error: undefined,
            login: () => { },
            logout: () => { },
            openSettings: () => { },
            roles: ["ADMIN", "MEMBER"],
            hasRole: (role: string) => ["ADMIN", "MEMBER"].includes(role),
            isAdmin: () => true,
        };
    }

    const auth = useOidcAuth();

    // Extract roles from ID token claims
    const getRoles = (): string[] => {
        const claims = auth.user?.profile;
        if (!claims) return [];

        // Zitadel stores roles in this claim
        const rolesObj = claims["urn:zitadel:iam:org:project:roles"] as
            | Record<string, unknown>
            | undefined;

        if (!rolesObj) return [];
        return Object.keys(rolesObj);
    };

    // Get avatar URL from Zitadel
    // Zitadel provides the picture in the 'picture' claim
    const getAvatar = (): string | undefined => {
        const claims = auth.user?.profile;
        if (!claims) return undefined;

        // Zitadel uses 'picture' claim for avatar URL
        return claims.picture as string | undefined;
    };

    // Check if user has a specific role
    const hasRole = (role: string): boolean => {
        return getRoles().includes(role);
    };

    // Check if user is admin
    const isAdmin = (): boolean => {
        return hasRole("ADMIN");
    };

    // Open Zitadel account settings in new tab
    const openSettings = (): void => {
        window.open(`${authority}/ui/console/users/me`, "_blank");
    };

    return {
        // User info
        user: auth.user?.profile,
        avatar: getAvatar(),
        accessToken: auth.user?.access_token,
        isAuthenticated: auth.isAuthenticated,
        isLoading: auth.isLoading,
        error: auth.error,

        // Auth actions
        login: () => auth.signinRedirect(),
        logout: () =>
            auth.signoutRedirect({
                post_logout_redirect_uri: `${window.location.origin}/logout`,
            }),
        openSettings,

        // Role helpers
        roles: getRoles(),
        hasRole,
        isAdmin,
    };
}

