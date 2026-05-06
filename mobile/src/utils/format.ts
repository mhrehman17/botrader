export const fmtMoney = (v: number, ccy = 'USD'): string => {
  const sign = v < 0 ? '-' : '';
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${sign}${ccy} ${(a / 1_000).toFixed(1)}k`;
  return `${sign}${ccy} ${a.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

export const fmtPct = (v: number, digits = 2): string =>
  `${v >= 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`;

export const fmtNum = (v: number, digits = 2): string =>
  v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const fmtTime = (tsMs: number): string => {
  const d = new Date(tsMs);
  return d.toLocaleString();
};
