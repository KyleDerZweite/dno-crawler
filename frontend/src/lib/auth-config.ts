/**
 * Zitadel OIDC Configuration
 *
 * Environment variables required:
 * - VITE_ZITADEL_AUTHORITY
 * - VITE_ZITADEL_CLIENT_ID
 * - VITE_ZITADEL_REDIRECT_URI
 * - VITE_ZITADEL_POST_LOGOUT_URI
 */
import { WebStorageStateStore } from "oidc-client-ts";

export const authConfig = {
    authority: import.meta.env.VITE_ZITADEL_AUTHORITY,
    client_id: import.meta.env.VITE_ZITADEL_CLIENT_ID,
    redirect_uri: import.meta.env.VITE_ZITADEL_REDIRECT_URI,
    post_logout_redirect_uri: import.meta.env.VITE_ZITADEL_POST_LOGOUT_URI,
    scope: "openid profile email",
    response_type: "code",
    // Use localStorage instead of sessionStorage so auth persists across tabs
    userStore: new WebStorageStateStore({ store: window.localStorage }),
    // PKCE is enabled by default in oidc-client-ts
};

// Validate config on load
const requiredVars = [
    "VITE_ZITADEL_AUTHORITY",
    "VITE_ZITADEL_CLIENT_ID",
    "VITE_ZITADEL_REDIRECT_URI",
    "VITE_ZITADEL_POST_LOGOUT_URI",
];

for (const varName of requiredVars) {
    if (!import.meta.env[varName]) {
        console.error(`Missing required environment variable: ${varName}`);
    }
}
