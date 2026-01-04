# DNO Crawler Frontend

React SPA for the DNO Crawler application.

## Stack

- **React 18** with TypeScript
- **Vite** for development and bundling
- **TailwindCSS** for styling
- **TanStack Query** for server state management
- **react-oidc-context** for OIDC authentication
- **Base UI** for accessible component primitives
- **React Router** for client-side routing

## Directory Structure

```
src/
├── pages/              # Page components (routes)
│   ├── LandingPage.tsx
│   ├── SearchPage.tsx
│   ├── DNOsPage.tsx
│   ├── DNODetailPage.tsx
│   ├── JobsPage.tsx
│   ├── JobDetailsPage.tsx
│   ├── AdminPage.tsx
│   └── SettingsPage.tsx
├── components/         # Reusable UI components
│   ├── Layout.tsx
│   ├── DataPreviewTables.tsx
│   ├── StatusBadge.tsx
│   └── ...
├── lib/                # Utilities and API client
│   ├── api.ts          # Axios API client
│   ├── api.types.ts    # TypeScript types for API
│   ├── auth.tsx        # Auth context and hooks
│   └── utils.ts
├── hooks/              # Custom React hooks
├── App.tsx             # Root component with routing
├── main.tsx            # Entry point
└── index.css           # Global styles and Tailwind
```

## Development

### Prerequisites

- Node.js 18+
- npm or pnpm

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The app runs at `http://localhost:5173` by default.

### Environment Variables

Create a `.env` file or set these in the root `.env`:

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL (default: `http://localhost:8000/api/v1`) |
| `VITE_ZITADEL_AUTHORITY` | OIDC provider URL (use `https://auth.example.com` for mock mode) |
| `VITE_ZITADEL_CLIENT_ID` | OIDC client ID |
| `VITE_ZITADEL_REDIRECT_URI` | OAuth callback URL |
| `VITE_ZITADEL_POST_LOGOUT_URI` | Post-logout redirect URL |

### Mock Authentication

When `VITE_ZITADEL_AUTHORITY` is set to `https://auth.example.com`, the app runs in mock mode with a pre-authenticated admin user. No real authentication flow is required.

## Build

```bash
# Production build
npm run build

# Preview production build
npm run preview
```

Output is generated in `dist/`.

## Key Features

### Authentication

The app uses `react-oidc-context` for OIDC authentication:

```tsx
import { useAuth } from 'react-oidc-context';

function MyComponent() {
  const auth = useAuth();
  
  if (auth.isLoading) return <Spinner />;
  if (!auth.isAuthenticated) return <LoginButton />;
  
  return <div>Welcome, {auth.user?.profile.email}</div>;
}
```

### API Client

TanStack Query handles data fetching with automatic caching:

```tsx
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';

// Fetch DNOs
const { data, isLoading } = useQuery({
  queryKey: ['dnos'],
  queryFn: () => api.get('/dnos').then(r => r.data)
});

// Trigger crawl
const mutation = useMutation({
  mutationFn: (dnoId: number) => api.post(`/dnos/${dnoId}/crawl`),
  onSuccess: () => queryClient.invalidateQueries(['dnos'])
});
```

### Routing

React Router handles client-side navigation:

| Route | Page | Auth |
|-------|------|------|
| `/` | LandingPage | Public |
| `/search` | SearchPage | Public |
| `/dnos` | DNOsPage | Protected |
| `/dnos/:id` | DNODetailPage | Protected |
| `/jobs` | JobsPage | Protected |
| `/jobs/:id` | JobDetailsPage | Protected |
| `/admin` | AdminPage | Admin |
| `/settings` | SettingsPage | Protected |

## Linting

```bash
# Run ESLint
npm run lint
```

## Docker

For containerized development:

```bash
# From project root
podman-compose up frontend
```

The frontend container watches for file changes and hot-reloads automatically.
