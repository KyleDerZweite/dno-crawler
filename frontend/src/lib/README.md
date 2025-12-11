# React SPA Auth Template

Copy-paste auth implementation for React + TypeScript + Vite applications using Zitadel.

## Files

| File | Purpose |
|------|---------|
| `auth-provider.tsx` | AuthProvider component with OIDC client |
| `auth-config.ts` | Zitadel configuration |
| `auth-callback.tsx` | Callback handler for login redirect |
| `use-auth.ts` | useAuth hook for accessing auth state |
| `protected-route.tsx` | Route wrapper for authenticated-only pages |
| `api.ts` | Axios instance with auth interceptor |
| `index.ts` | Barrel exports |

## Installation

```bash
npm install oidc-client-ts react-oidc-context
```

## Setup

1. Copy all files to your `src/lib/auth/` directory
2. Create a `.env` file with your Zitadel settings:

```
VITE_ZITADEL_AUTHORITY=https://auth.kylehub.dev
VITE_ZITADEL_CLIENT_ID=your-client-id
VITE_ZITADEL_REDIRECT_URI=http://localhost:5173/callback
VITE_ZITADEL_POST_LOGOUT_URI=http://localhost:5173
```

3. Wrap your app with AuthProvider in `main.tsx`
4. Add the callback route to your router
5. Use the `useAuth` hook in components

## Usage

### Basic Login/Logout

```tsx
import { useAuth } from './lib/auth';

function MyComponent() {
    const { user, isAuthenticated, login, logout, hasRole } = useAuth();

    if (!isAuthenticated) {
        return <button onClick={login}>Login</button>;
    }

    return (
        <div>
            <p>Welcome, {user?.email}</p>
            {hasRole('ADMIN') && <AdminPanel />}
            <button onClick={logout}>Logout</button>
        </div>
    );
}
```

### User Avatar

The avatar is automatically fetched from Zitadel if the user has set a profile picture:

```tsx
function UserMenu() {
    const { user, avatar, logout, openSettings } = useAuth();

    return (
        <div className="flex items-center gap-2">
            {avatar ? (
                <img
                    src={avatar}
                    alt={user?.name}
                    className="w-8 h-8 rounded-full"
                />
            ) : (
                <div className="w-8 h-8 rounded-full bg-gray-300" />
            )}
            <span>{user?.name}</span>
            <button onClick={openSettings}>Settings</button>
            <button onClick={logout}>Logout</button>
        </div>
    );
}
```

### Account Settings

The `openSettings()` function opens the Zitadel console where users can:
- Update their profile picture
- Change their password
- Manage their account

This links to `https://auth.kylehub.dev/ui/console/users/me`.

