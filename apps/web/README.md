# EventPass Web

Vite/React web client for organizer administration and shareable social resale campaign pages. Run `npm install` once, then `npm run dev` to serve on port 8000. It proxies API requests to FastAPI at `http://127.0.0.1:8001` by default; set `EVENTPASS_API_PROXY_TARGET` to override the API origin.

Run `npm run build` to build the production web assets into `backend/static`. FastAPI serves those assets and the public `/c/:slug` campaign landing pages in production.
