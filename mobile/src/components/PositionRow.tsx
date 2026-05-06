import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { Position } from '../api/client';
import { colors, radii, space, text } from '../theme';
import { fmtMoney, fmtNum } from '../utils/format';

export const PositionRow: React.FC<{ p: Position }> = ({ p }) => {
  const tint = p.side === 'long' ? colors.green : colors.red;
  const upnlTone = p.unrealized_pnl >= 0 ? colors.green : colors.red;
  return (
    <View style={styles.row}>
      <View style={styles.head}>
        <View style={[styles.sideChip, { borderColor: tint }]}>
          <Text style={{ color: tint, fontWeight: '700', fontSize: 11 }}>
            {p.side.toUpperCase()}
          </Text>
        </View>
        <Text style={[text.body, { fontWeight: '700' }]}>{p.symbol}</Text>
        <Text style={[text.mono, { color: upnlTone }]}>{fmtMoney(p.unrealized_pnl)}</Text>
      </View>
      <View style={styles.body}>
        <Text style={text.muted}>entry {fmtNum(p.entry_price, 4)}</Text>
        <Text style={text.muted}>SL {p.stop_loss ? fmtNum(p.stop_loss, 4) : '--'}</Text>
        <Text style={text.muted}>TP {p.take_profit ? fmtNum(p.take_profit, 4) : '--'}</Text>
        <Text style={text.muted}>qty {fmtNum(p.qty, 4)}</Text>
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
  head: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
  sideChip: {
    borderWidth: 1,
    paddingHorizontal: space(2),
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  body: { flexDirection: 'row', justifyContent: 'space-between', marginTop: space(2) },
});
