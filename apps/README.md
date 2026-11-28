# EventPass clients

- `mobile/` is the Expo React Native attendee, seller, and gate scanner app. Its local Expo server uses port 8081.
- `web/` is the Vite browser app for public social resale campaign pages and the organizer dashboard. Its local development server uses port 8000.
- `../backend/` is the shared FastAPI API. Run it on port 8001 for local development. The Vite app proxies `/api/*` requests to it.

The Vite production build is emitted to `backend/static` for the existing FastAPI deployment. The Expo mobile app is a separate deployable client.
