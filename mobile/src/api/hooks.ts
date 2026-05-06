/** React Query hooks. All polling intervals are conservative; tune per screen. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  api,
  CandlesResponse,
  ConfigOut,
  CredentialPublic,
  EquityPoint,
  EquitySnapshot,
  Health,
  KillSwitchOut,
  Mode,
  Position,
  ScanRow,
  ServerInfo,
  Trade,
} from './client';

export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/healthz'), refetchInterval: 5000 });

export const useEquity = () =>
  useQuery({ queryKey: ['equity'], queryFn: () => api<EquitySnapshot>('/equity'), refetchInterval: 5000 });

export const useEquityCurve = (n = 200) =>
  useQuery({
    queryKey: ['equity-curve', n],
    queryFn: () => api<EquityPoint[]>(`/equity-curve?n=${n}`),
    refetchInterval: 10000,
  });

export const usePositions = () =>
  useQuery({ queryKey: ['positions'], queryFn: () => api<Position[]>('/positions'), refetchInterval: 5000 });

export const useTrades = (limit = 50) =>
  useQuery({
    queryKey: ['trades', limit],
    queryFn: () => api<Trade[]>(`/trades?limit=${limit}`),
    refetchInterval: 10000,
  });

export const useScan = () =>
  useQuery({ queryKey: ['scan'], queryFn: () => api<ScanRow[]>('/scan'), refetchInterval: 15000 });

export const useCandles = (symbol: string, tf: string, limit = 200) =>
  useQuery({
    queryKey: ['candles', symbol, tf, limit],
    queryFn: () => api<CandlesResponse>(`/candles?symbol=${encodeURIComponent(symbol)}&tf=${tf}&limit=${limit}&overlays=1`),
    refetchInterval: 15000,
  });

export const useKillSwitch = () =>
  useQuery({ queryKey: ['killswitch'], queryFn: () => api<KillSwitchOut>('/killswitch'), refetchInterval: 5000 });

export const useConfig = () =>
  useQuery({ queryKey: ['config'], queryFn: () => api<ConfigOut>('/config') });

export const useServerInfo = () =>
  useQuery({ queryKey: ['server-info'], queryFn: () => api<ServerInfo>('/server-info') });

export const useCredentials = () =>
  useQuery({ queryKey: ['credentials'], queryFn: () => api<CredentialPublic[]>('/credentials') });

export const useStartBot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api('/bot/start', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['health'] }),
  });
};

export const useStopBot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api('/bot/stop', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['health'] }),
  });
};

export const useSwitchMode = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { mode: Mode; confirm?: string; exchange_id?: string }) =>
      api('/bot/mode', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['health'] }),
  });
};

export const useUpsertCredential = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      exchange_id: string;
      api_key: string;
      api_secret: string;
      testnet: boolean;
      label?: string;
    }) =>
      api(`/credentials/${body.exchange_id}`, {
        method: 'PUT',
        body: JSON.stringify({
          api_key: body.api_key,
          api_secret: body.api_secret,
          testnet: body.testnet,
          label: body.label || '',
        }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
};

export const useDeleteCredential = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/credentials/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
};

export const useVerifyCredential = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/credentials/${id}/verify`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
};

export const usePatchConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: { risk?: Record<string, number>; strategy?: Record<string, number> }) =>
      api('/config', { method: 'PUT', body: JSON.stringify(patch) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  });
};
