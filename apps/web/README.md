# EventPass Web

Vite/React web client for organizer administration and shareable social resale campaign pages. Run `npm install` once, then `npm run dev` to serve on port 8000. It proxies API requests to FastAPI at `http://127.0.0.1:8001` by default; set `EVENTPASS_API_PROXY_TARGET` to override the local API origin. For production, copy `.env.example`, set `VITE_API_BASE_URL` to the FastAPI origin, and allow this web origin in the backend CORS configuration.

Run `npm run build` to build Vercel-ready assets into `dist`. Deploy with Root Directory `apps/web`, Build Command `npm run build`, and Output Directory `dist`. `vercel.json` rewrites `/c/:slug` to the SPA entry so shared campaign links open directly.

For the optional legacy deployment that serves the web client from FastAPI, run `npm run build:fastapi`; that build emits `/static/` assets to `../../backend/static`.
