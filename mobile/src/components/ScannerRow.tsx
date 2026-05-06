import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { ScanRow as ScanRowT } from '../api/client';
import { colors, radii, space, text } from '../theme';
import { fmtNum } from '../utils/format';

const stateTint = (s: string) =>
  s === 'armed' ? colors.green : s.startsWith('waiting') ? colors.amber : colors.muted;

const biasArrow = (b: string) => (b === 'up' ? '▲' : b === 'down' ? '▼' : '—');
const biasTint = (b: string) => (b === 'up' ? colors.green : b === 'down' ? colors.red : colors.muted);

export const ScannerRow: React.FC<{ r: ScanRowT }> = ({ r }) => {
  const dist =
    r.target_price && r.last_close
      ? `${((Math.abs(r.target_price - r.last_close) / r.last_close) * 100).toFixed(2)}%`
      : '--';
  return (
    <View style={[styles.row, { borderColor: stateTint(r.state) }]}>
      <View style={styles.head}>
        <Text style={[styles.bias, { color: biasTint(r.bias) }]}>{biasArrow(r.bias)}</Text>
        <Text style={[text.body, { fontWeight: '700', flex: 1 }]}>{r.symbol}</Text>
        <Text style={[styles.state, { color: stateTint(r.state) }]}>{r.state}</Text>
      </View>
      <View style={styles.body}>
        <Text style={text.muted}>last {fmtNum(r.last_close, 4)}</Text>
        <Text style={text.muted}>
          target {r.target_price ? fmtNum(r.target_price, 4) : '--'}
        </Text>
        <Text style={text.muted}>dist {dist}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(3),
    marginBottom: space(2),
  },
  head: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
  bias: { fontSize: 18, marginRight: 4 },
  state: { fontSize: 11, fontWeight: '700', letterSpacing: 0.8 },
  body: { flexDirection: 'row', justifyContent: 'space-between', marginTop: space(2) },
});
