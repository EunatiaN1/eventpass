# EventPass — Architecture & Project Context

EventPass is a mobile-first ticketing platform for discovering events, buying and holding passes, reselling tickets through shareable campaigns, and validating entry. This repository keeps its attendee app, browser app, and API separate. Read this map before changing app code; do not mix mobile and web dependencies or build targets.

## Product experience

- **Mobile is primary.** Attendees, sellers, and gate operators use the Expo app. The visual system is dark and premium: `#0A0A0A`, glass surfaces, orange actions (`#FF6B00`), emerald success (`#00E676`), Expo Blur, and Reanimated motion.
- **Sign-in is passwordless.** Users enter an email, receive a six-digit code, and verify it. Wallet signatures are not required to sign in. Native sessions use Expo SecureStore.
- **Attendees** browse event cards, buy passes, view ticket QR credentials, and access account-protected features.
- **Sellers** list eligible tickets and share social resale campaign links.
- **Gate operators** use the authenticated mobile scanner to validate signed QR credentials for an event.
- **The browser app serves two audiences:** buyers opening public resale campaign links, and organizers managing event settings and reviewing the ledger on desktop.
- **Payments in the checkout UI are simulations.** The EFT/card/x402 demo screens do not collect or transmit real card details and must not claim that money or an on-chain transfer occurred. Keep demo and settlement states clearly distinguished.

## Repository layout

```text
eventpass/
├── apps/
│   ├── mobile/       Expo React Native app (attendees, sellers, gate scanner)
│   └── web/          Vite/React browser app (campaign pages, organizer dashboard)
├── backend/          FastAPI API and services
└── README.md
```

| App | Development URL | Main use |
| --- | --- | --- |
| Expo mobile | `http://localhost:8081` | Attendees, sellers, and gate scanner |
| Vite web | `http://localhost:8000` | Social resale campaigns and organizer dashboard |
| FastAPI | `http://localhost:8001` | Shared API in local development |

## App responsibilities

### `apps/mobile` — primary attendee and operations app

- Expo Router screens for Events, My Tickets, Resale, and Gate.
- Two-column event browsing with Expo Image, gradient overlays, and animated press/entry states.
- Glassmorphic email OTP modal with a six-digit input, resend cooldown, inline errors, and Reanimated transitions.
- Secure native session persistence with Expo SecureStore.
- Digital ticket passes show a signed QR credential and account details.
- Gate scanning uses Expo Camera and the authenticated `/api/check-in` endpoint.
- Checkout methods are EFT, card, and x402 demonstration flows. Do not collect real payment credentials in these screens.

Use Expo-compatible native libraries only in this app. Build iOS and Android with Expo/EAS workflows; **do not select `apps/mobile` as a Vercel web project.**

### `apps/web` — public links and organizer desktop app

- Public campaign pages use `/c/:slug`; buyers can open these links in a browser without installing the mobile app.
- Organizer screens manage event resale policies and view ledger activity.
- Uses React, Vite, Tailwind CSS, and browser libraries. Do not import React Native or Expo UI packages here.
- Uses `VITE_API_BASE_URL` for a separately hosted API. Leave it blank for local development, where Vite proxies `/api/*` to FastAPI.

### `backend` — shared FastAPI service

- Passwordless email OTP endpoints: `/api/auth/otp`, `/api/auth/verify-otp`, `/api/auth/me`, and `/api/auth/sign-out`.
- Event, ticket, resale campaign, checkout, refund, x402, ledger, webhook, and check-in routes are under `/api`.
- Browser auth uses an HttpOnly session cookie; native auth receives a bearer session token and stores it in SecureStore.
- Supabase service credentials, Resend credentials, payment provider secrets, and Solana private keys belong only in backend secrets. Never expose these as `VITE_` or `EXPO_PUBLIC_` variables.
- `backend/services/solana.py` calls the EventPass Anchor program for event initialization, Core ticket minting, and check-in. Resale asset transfers remain disabled until transfer delegation is implemented and deployed.

The Anchor program source is in `anchor/` and includes event initialization, Metaplex Core ticket minting, and check-in instructions. It has not been built or deployed to Devnet yet. The backend will refuse chain operations until a generated program keypair is deployed and its program ID and authority are configured. See `anchor/README.md` for deployment steps. The browser still needs a wallet connection and PayFast redirect flow before purchases can use this backend.

## Local development

1. Run FastAPI from the repository root: `python3 -m uvicorn backend.main:app --port 8001`.
2. Run the browser app: `cd apps/web && npm install && npm run dev`.
3. Run the mobile app: `cd apps/mobile && npm install && npm run start -- --port 8081`.

For a physical phone, set `EXPO_PUBLIC_API_URL` in `apps/mobile/.env` to the development machine’s LAN address and port `8001`. The standard Android emulator uses `http://10.0.2.2:8001`. For a deployed API, configure `VITE_API_BASE_URL` for the web app and `EXPO_PUBLIC_API_URL` for mobile. Add the deployed browser origin to the backend `ALLOWED_ORIGINS` list.

## Deployment boundaries

### Vercel: deploy the browser app only

Create a Vercel project with Root Directory `apps/web`, Framework Preset `Vite`, Build Command `npm run build`, and Output Directory `dist`. The normal Vite build emits to `apps/web/dist`; the `/c/:slug` rewrite keeps direct social campaign links working. Configure `VITE_API_BASE_URL` to the deployed FastAPI origin.

Do not point this Vercel project at `apps/mobile`. Expo native builds are produced for iOS and Android separately. Vercel’s current Python runtime can run FastAPI, but this repository has no backend-specific Vercel project configuration; deploy the API separately and verify its entry point, dependencies, secrets, and runtime limits for the selected host.

### Optional legacy FastAPI-hosted web bundle

For an environment that intentionally serves the browser UI from FastAPI’s `backend/static`, use `cd apps/web && npm run build:fastapi`. This is separate from the default Vercel build and writes assets under `/static/`.

### Expo native builds

Use Expo/EAS for iOS and Android builds. Keep API keys and signing credentials in backend or build-service secret storage; `EXPO_PUBLIC_*` values are bundled into the client and are public.

## Engineering rules

1. Check the path before editing: `apps/mobile`, `apps/web`, or `backend`.
2. Keep frontend dependencies isolated. Never import `expo-blur` into the Vite app or browser routing packages into Expo screens.
3. Preserve the Apple-luxury visual tokens and passwordless OTP flow in mobile UI work.
4. Use mock data only when it is clearly labelled as demo data; never present a simulation as real payment or chain settlement.
5. When a flow is not connected to a verified provider or deployed program, describe the gap accurately instead of implying that the feature is live.
