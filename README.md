# EventPass

EventPass is organized as separate mobile and web clients over the existing FastAPI service.

| App | Path | Local address | Main use |
| --- | --- | --- | --- |
| Expo mobile | `apps/mobile` | `http://localhost:8081` | Attendees, sellers, and gate check-in |
| Vite web | `apps/web` | `http://localhost:8000` | Public resale campaign links and organizer administration |
| FastAPI | `backend` | `http://localhost:8001` (development) | Shared API and production web asset serving |

## Local development

Start FastAPI on port 8001 with `python3 -m uvicorn backend.main:app --port 8001`. Start the web client with `cd apps/web && npm run dev`; start Expo with `cd apps/mobile && npm run start`.

The Vite development server proxies `/api/*` to FastAPI. In production, the Vite build is emitted to `backend/static` for the existing FastAPI deployment. Social campaign paths such as `/c/:slug` remain browser accessible.

The mobile client uses passwordless email OTP. Native session tokens are stored using Expo SecureStore. Configure `EXPO_PUBLIC_API_URL` in `apps/mobile/.env` for physical devices or a deployed API; never place server secrets in Expo public environment variables.
