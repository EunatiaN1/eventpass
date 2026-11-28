# EventPass clients

- `mobile/` is the Expo React Native attendee, seller, and gate scanner app. Its local Expo server uses port 8081.
- `web/` is the Vite browser app for public social resale campaign pages and the organizer dashboard. Its local development server uses port 8000.
- `../backend/` is the shared FastAPI API. Run it on port 8001 for local development. The Vite app proxies `/api/*` requests to it.

The standard Vite build outputs to `apps/web/dist` for Vercel. Use `npm run build:fastapi` only for the optional legacy FastAPI-hosted web bundle. The Expo app is built separately with Expo/EAS and is not a Vercel web deployment.
