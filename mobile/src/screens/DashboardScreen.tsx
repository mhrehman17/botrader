import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { EquityChart } from '../components/EquityChart';
import { KillSwitchBadge } from '../components/KillSwitchBadge';
import { ModeChip } from '../components/ModeChip';
import { ModeSwitcherSheet } from '../components/ModeSwitcherSheet';
import { PositionRow } from '../components/PositionRow';
import { StatPill } from '../components/StatPill';
import {
  useEquity,
  useEquityCurve,
  useHealth,
  usePositions,
  useStartBot,
  useStopBot,
} from '../api/hooks';
import { colors, radii, space, text } from '../theme';
import { fmtMoney, fmtPct } from '../utils/format';

export const DashboardScreen: React.FC = () => {
  const { data: health } = useHealth();
  const { data: eq } = useEquity();
  const { data: curve } = useEquityCurve(200);
  const { data: positions } = usePositions();
  const startBot = useStartBot();
  const stopBot = useStopBot();
  const [modeSheet, setModeSheet] = useState(false);

  const dailyPctTone = (eq?.daily_pnl ?? 0) >= 0 ? 'pos' : 'neg';
  const ddPct =
    eq && eq.peak_equity > 0 ? (eq.peak_equity - eq.equity) / eq.peak_equity : 0;

  return (
    <SafeAreaView style={styles.bg} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: space(4) }}>
        <View style={styles.header}>
          <Text style={text.h2}>botrader</Text>
          <View style={{ flexDirection: 'row', gap: space(2), alignItems: 'center' }}>
            <KillSwitchBadge />
            <ModeChip mode={health?.mode ?? null} onPress={() => setModeSheet(true)} />
          </View>
        </View>

        <View style={styles.heroCard}>
          <Text style={text.muted}>Equity</Text>
          <Text style={text.monoLg}>{eq ? fmtMoney(eq.equity) : '— —'}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space(2), marginTop: space(1) }}>
            <View
              style={[
                styles.pnlChip,
                {
                  backgroundColor: dailyPctTone === 'pos' ? colors.green : colors.red,
                },
              ]}
            >
              <Text style={styles.pnlChipText}>
                {fmtMoney(eq?.daily_pnl ?? 0)} today
              </Text>
            </View>
            <Text style={text.muted}>peak {eq ? fmtMoney(eq.peak_equity) : '--'}</Text>
          </View>

          <View style={{ marginTop: space(3) }}>
            <EquityChart data={curve ?? []} />
          </View>
        </View>

        <View style={styles.botRow}>
          <Text style={text.body}>Bot</Text>
          <Switch
            value={!!health?.running}
            onValueChange={(v) => (v ? startBot.mutate() : stopBot.mutate())}
            disabled={startBot.isPending || stopBot.isPending}
            trackColor={{ true: colors.green, false: colors.muted }}
          />
        </View>

        <View style={styles.statsRow}>
          <StatPill label="Open positions" value={String(positions?.length ?? 0)} />
          <StatPill
            label="Daily PnL"
            value={fmtMoney(eq?.daily_pnl ?? 0)}
            tone={dailyPctTone as 'pos' | 'neg'}
          />
          <StatPill
            label="Drawdown"
            value={fmtPct(-ddPct, 2)}
            tone={ddPct > 0 ? 'neg' : 'neutral'}
          />
        </View>

        <Text style={[text.h2, { marginTop: space(5), marginBottom: space(2) }]}>
          Top positions
        </Text>
        {(positions ?? []).slice(0, 3).map((p) => (
          <PositionRow key={p.symbol} p={p} />
        ))}
        {!positions?.length && (
          <Pressable style={styles.empty}>
            <Text style={text.muted}>No open positions.</Text>
          </Pressable>
        )}
      </ScrollView>

      <ModeSwitcherSheet
        visible={modeSheet}
        current={health?.mode ?? null}
        onClose={() => setModeSheet(false)}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: space(4),
  },
  heroCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.lg,
    padding: space(4),
  },
  pnlChip: { paddingHorizontal: space(2), paddingVertical: 2, borderRadius: radii.sm },
  pnlChipText: { color: '#0a0a0c', fontWeight: '700', fontSize: 11 },
  botRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderColor: colors.border,
    borderWidth: 1,
    paddingHorizontal: space(4),
    paddingVertical: space(3),
    marginTop: space(4),
  },
  statsRow: { flexDirection: 'row', marginTop: space(3) },
  empty: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(4),
    alignItems: 'center',
  },
});
