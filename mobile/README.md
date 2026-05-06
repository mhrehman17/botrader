# botrader mobile

Native cross-platform mobile UI for the SMC futures bot. Built with Expo + React Native + TypeScript.

## Prerequisites

- Node 18+ and npm.
- Install Expo Go on your phone (iOS App Store / Google Play).
- Backend running: `botrader serve --config configs/paper.yaml --port 8787` with `BOTRADER_API_TOKEN` and `BOTRADER_MASTER_KEY` env vars set.

## Run

```bash
cp .env.example .env
# Edit .env: set EXPO_PUBLIC_API_URL to your server's LAN address (e.g. http://192.168.1.10:8787)
# and EXPO_PUBLIC_API_TOKEN to the same value as the server's BOTRADER_API_TOKEN.

npm install
npm run start
```

Scan the QR with Expo Go.

## Screens

- **Dashboard** — equity, daily PnL, sparkline, mode pill (tap to switch), bot on/off, top positions.
- **Positions** — open positions with entry / SL / TP / qty / unrealized PnL.
- **Scanner** — per-symbol HTF bias, LTF state-machine state, target liquidity.
- **Chart** — 200 LTF candles with OB / FVG / sweep overlays toggleable per layer.
- **History** — closed trades filtered by reason (TP1, TP2, SL, BE) with cumulative R, win-rate, profit factor.
- **Settings** — API keys management (add / verify / delete), mode switcher, risk + strategy patches with mainnet write-lock.

## Security

- Bearer token from `EXPO_PUBLIC_API_TOKEN` is bundled into the app binary. **Personal use only.** Don't ship to public app stores.
- Exchange API keys are sent over the bearer-authenticated channel, encrypted at rest server-side via Fernet, and never returned to the device.
- Mainnet mode requires the server to be started with `BOTRADER_ALLOW_MAINNET=1` AND a typed `MAINNET` confirmation.
- For LAN use only. To go remote, put a reverse proxy with TLS in front and IP-allowlist your phone.

## Disclaimer

This is not financial advice. Trading bots can and do lose money. Backtest, walk-forward, and paper-trade before risking real capital.
