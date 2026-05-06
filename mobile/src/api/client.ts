/** Bearer-authenticated fetch client with 8s timeout. */
import Constants from 'expo-constants';

type FetchOpts = RequestInit & { timeout?: number };

const API_URL: string =
  process.env.EXPO_PUBLIC_API_URL ||
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ||
  'http://127.0.0.1:8787';

const API_TOKEN: string = process.env.EXPO_PUBLIC_API_TOKEN || '';

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export async function api<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeout ?? 8000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...opts,
      signal: ctrl.signal,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${API_TOKEN}`,
        ...(opts.headers || {}),
      },
    });
    if (!res.ok) {
      let detail: unknown = await res.text();
      try {
        detail = JSON.parse(detail as string);
      } catch {
        // keep as text
      }
      throw new ApiError(res.status, detail, `HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

// Typed responses (mirror api/schemas.py — keep in sync).
export type Mode = 'paper' | 'testnet' | 'mainnet';

export type Health = {
  ok: boolean;
  mode: Mode | null;
  running: boolean;
  started_at: number;
  version: string;
};

export type EquitySnapshot = {
  equity: number;
  cash: number;
  upnl: number;
  daily_pnl: number;
  peak_equity: number;
  initial_equity: number;
};

export type EquityPoint = { ts: number; equity: number; cash: number; upnl: number };

export type Position = {
  symbol: string;
  side: 'long' | 'short';
  qty: number;
  entry_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  unrealized_pnl: number;
  leverage: number;
  opened_ts: number;
};

export type Trade = {
  symbol: string;
  side: 'long' | 'short';
  entry_ts: number;
  exit_ts: number;
  entry_price: number;
  exit_price: number;
  qty: number;
  pnl: number;
  fees: number;
  r_multiple: number;
  reason: string;
};

export type ScanRow = {
  symbol: string;
  bias: 'up' | 'down' | 'none';
  state: string;
  target_price: number | null;
  last_close: number;
  ts: number;
};

export type CredentialPublic = {
  id: string;
  has_key: boolean;
  label: string;
  testnet: boolean;
  created_at: number | null;
  last_verified_at: number | null;
};

export type ServerInfo = { allow_mainnet: boolean; version: string };

export type CandlesResponse = {
  symbol: string;
  tf: string;
  candles: { ts: number; open: number; high: number; low: number; close: number; volume: number }[];
  overlays: {
    order_blocks: { idx: number; ts: number; top: number; bottom: number; side: 'long' | 'short'; mitigated: boolean }[];
    fvgs: { idx: number; ts: number; top: number; bottom: number; side: 'long' | 'short'; filled: boolean }[];
    sweeps: { idx: number; ts: number; pool_price: number; is_high: boolean; extreme: number; close: number }[];
  };
};

export type ConfigOut = {
  mode: string;
  symbols: string[];
  timeframes: { htf: string; ltf: string };
  strategy: Record<string, number | string>;
  risk: Record<string, number | string>;
  exchange: { id: string; testnet: boolean; api_key: string; api_secret: string };
};

export type KillSwitchOut = {
  tripped: boolean;
  reason: string;
  peak_equity: number;
  day_start_equity: number;
};
