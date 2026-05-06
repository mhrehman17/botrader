/** Dark-trader theme: terminal-inspired palette + monospace numerics. */
export const colors = {
  bg: '#0a0a0c',
  surface: '#13141a',
  surfaceAlt: '#181a22',
  border: '#1f2128',
  text: '#e6e6e6',
  muted: '#7d7d8a',
  accent: '#5b9eff',
  green: '#00d97e',
  red: '#ff5263',
  amber: '#ffb547',
  paper: '#5b9eff',
  testnet: '#ffb547',
  mainnet: '#ff5263',
};

export const radii = { sm: 6, md: 10, lg: 16, pill: 999 };

export const space = (n: number) => n * 4;

export const fonts = {
  body: undefined as string | undefined, // system
  mono: 'Menlo' as string | undefined,   // iOS; RN falls back gracefully on Android
};

export const text = {
  h1: { fontSize: 28, fontWeight: '700' as const, color: colors.text },
  h2: { fontSize: 20, fontWeight: '700' as const, color: colors.text },
  body: { fontSize: 14, color: colors.text },
  muted: { fontSize: 12, color: colors.muted },
  mono: { fontFamily: fonts.mono, fontSize: 14, color: colors.text },
  monoLg: { fontFamily: fonts.mono, fontSize: 32, fontWeight: '600' as const, color: colors.text },
};
