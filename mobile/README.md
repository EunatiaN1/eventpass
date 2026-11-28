# EventPass Mobile

Expo Router client for iOS, Android, and web. It uses the existing FastAPI API and keeps the current EventPass website intact.

## Run locally

1. Copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_URL` to the backend origin. Use your computer's LAN IP for a physical phone, or `http://10.0.2.2:8000` for the standard Android emulator.
2. Run `npm install` and `npm run start`.
3. Use `npm run ios`, `npm run android`, or `npm run web` to start a platform target.

The only client environment value is the public API origin. Email delivery credentials and the x402 destination configuration stay on the backend. Native OTP sessions are stored with Expo SecureStore.

## Verify

- `npm run typecheck`
- `npm run lint`
- `npm run build`

Checkout actions are demonstrations. The client does not transmit card details or claim to verify bank or blockchain settlement.
