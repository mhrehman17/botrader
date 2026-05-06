import React, { useMemo, useState } from 'react';
import { FlatList, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { TradeRow } from '../components/TradeRow';
import { useTrades } from '../api/hooks';
import { colors, radii, space, text } from '../theme';
import { fmtMoney, fmtNum } from '../utils/format';

const filters = [
  { id: 'all', label: 'All' },
  { id: 'tp1', label: 'TP1', match: (r: string) => r === 'take_profit_1' },
  { id: 'tp2', label: 'TP2', match: (r: string) => r === 'take_profit' },
  { id: 'sl', label: 'SL', match: (r: string) => r === 'stop_loss' },
  { id: 'be', label: 'BE', match: (r: string) => r === 'breakeven' },
];

export const HistoryScreen: React.FC = () => {
  const { data: trades } = useTrades(200);
  const [filter, setFilter] = useState<string>('all');

  const filtered = useMemo(() => {
    if (!trades) return [];
    if (filter === 'all') return trades;
    const def = filters.find((f) => f.id === filter);
    return def?.match ? trades.filter((t) => def.match!(t.reason)) : trades;
  }, [trades, filter]);

  const stats = useMemo(() => {
    if (!filtered.length) return { sumR: 0, win: 0, total: 0, pf: 0 };
    const wins = filtered.filter((t) => t.pnl > 0);
    const losses = filtered.filter((t) => t.pnl <= 0);
    const gp = wins.reduce((s, t) => s + t.pnl, 0);
    const gl = -losses.reduce((s, t) => s + t.pnl, 0);
    return {
      sumR: filtered.reduce((s, t) => s + t.r_multiple, 0),
      win: wins.length / filtered.length,
      total: filtered.reduce((s, t) => s + t.pnl, 0),
      pf: gl > 0 ? gp / gl : Infinity,
    };
  }, [filtered]);

  return (
    <SafeAreaView style={styles.bg} edges={['top']}>
      <View style={styles.header}>
        <Text style={text.h2}>History</Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
        {filters.map((f) => (
          <Pressable
            key={f.id}
            onPress={() => setFilter(f.id)}
            style={[
              styles.chip,
              { borderColor: filter === f.id ? colors.accent : colors.border },
            ]}
          >
            <Text
              style={{
                color: filter === f.id ? colors.accent : colors.muted,
                fontWeight: '700',
                fontSize: 12,
              }}
            >
              {f.label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      <View style={styles.stats}>
        <Text style={text.muted}>net {fmtMoney(stats.total)}</Text>
        <Text style={text.muted}>R {fmtNum(stats.sumR, 2)}</Text>
        <Text style={text.muted}>win {(stats.win * 100).toFixed(0)}%</Text>
        <Text style={text.muted}>
          PF {stats.pf === Infinity ? '∞' : fmtNum(stats.pf, 2)}
        </Text>
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={{ padding: space(4) }}
        renderItem={({ item }) => <TradeRow t={item} />}
        ListEmptyComponent={
          <Text style={[text.muted, { textAlign: 'center', marginTop: space(8) }]}>
            No trades yet.
          </Text>
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: space(4), paddingTop: space(2) },
  filters: { paddingHorizontal: space(4), paddingVertical: space(3), gap: space(2) },
  chip: {
    paddingHorizontal: space(3),
    paddingVertical: space(1),
    borderRadius: radii.pill,
    borderWidth: 1,
    backgroundColor: colors.surface,
    marginRight: space(2),
  },
  stats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: space(4),
    paddingVertical: space(2),
    backgroundColor: colors.surface,
    borderTopColor: colors.border,
    borderTopWidth: 1,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
  },
});
