import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { Trade } from '../api/client';
import { colors, radii, space, text } from '../theme';
import { fmtMoney, fmtNum, fmtTime } from '../utils/format';

const reasonColor = (r: string) =>
  r.startsWith('take_profit') ? colors.green :
  r === 'stop_loss' ? colors.red :
  r === 'breakeven' ? colors.amber : colors.muted;

export const TradeRow: React.FC<{ t: Trade }> = ({ t }) => {
  const pnlTone = t.pnl >= 0 ? colors.green : colors.red;
  return (
    <View style={styles.row}>
      <View style={styles.head}>
        <Text style={[text.body, { fontWeight: '700' }]}>{t.symbol}</Text>
        <Text style={text.muted}>{fmtTime(t.exit_ts)}</Text>
        <Text style={[text.mono, { color: pnlTone }]}>{fmtMoney(t.pnl)}</Text>
      </View>
      <View style={styles.body}>
        <Text style={[styles.reason, { color: reasonColor(t.reason) }]}>{t.reason}</Text>
        <Text style={text.muted}>R {fmtNum(t.r_multiple, 2)}</Text>
        <Text style={text.muted}>{t.side.toUpperCase()} {fmtNum(t.qty, 4)}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(3),
    marginBottom: space(2),
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  body: { flexDirection: 'row', justifyContent: 'space-between', marginTop: space(2) },
  reason: { fontSize: 11, fontWeight: '700', letterSpacing: 0.6 },
});
