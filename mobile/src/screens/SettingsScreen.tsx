import React, { useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CredentialsForm } from '../components/CredentialsForm';
import { ModeChip } from '../components/ModeChip';
import { ModeSwitcherSheet } from '../components/ModeSwitcherSheet';
import {
  useConfig,
  useCredentials,
  useDeleteCredential,
  useHealth,
  usePatchConfig,
  useVerifyCredential,
} from '../api/hooks';
import { colors, radii, space, text } from '../theme';
import { fmtNum } from '../utils/format';

const RISK_FIELDS: { key: string; label: string; min: number; max: number; step: number }[] = [
  { key: 'risk_pct_per_trade', label: 'Risk %/trade', min: 0.0005, max: 0.05, step: 0.0005 },
  { key: 'max_leverage', label: 'Max leverage', min: 1, max: 25, step: 1 },
  { key: 'max_concurrent_positions', label: 'Max positions', min: 1, max: 10, step: 1 },
  { key: 'daily_loss_kill_pct', label: 'Daily kill %', min: 0.005, max: 0.25, step: 0.005 },
  { key: 'max_drawdown_kill_pct', label: 'Max DD %', min: 0.01, max: 0.5, step: 0.01 },
  { key: 'trail_atr_mult', label: 'Trail ATR×', min: 0, max: 5, step: 0.1 },
];

const STRAT_FIELDS = [
  { key: 'partial_tp_pct', label: 'TP1 partial %', min: 0, max: 1, step: 0.05 },
  { key: 'ote_depth', label: 'OTE depth', min: 0, max: 1, step: 0.01 },
  { key: 'entry_ttl_bars', label: 'Entry TTL bars', min: 1, max: 100, step: 1 },
];

export const SettingsScreen: React.FC = () => {
  const { data: cfg } = useConfig();
  const { data: health } = useHealth();
  const { data: creds } = useCredentials();
  const patch = usePatchConfig();
  const verify = useVerifyCredential();
  const del = useDeleteCredential();
  const [showCredForm, setShowCredForm] = useState(false);
  const [showModeSheet, setShowModeSheet] = useState(false);

  const lockMainnet = health?.mode === 'mainnet' && health?.running;

  const updateRisk = async (k: string, v: number) => {
    try {
      await patch.mutateAsync({ risk: { [k]: v } });
    } catch (e: unknown) {
      const detail = (e as { detail?: { detail?: string } | string })?.detail ?? String(e);
      const msg = typeof detail === 'string' ? detail : detail?.detail ?? 'Failed';
      Alert.alert('Update failed', msg);
    }
  };
  const updateStrat = async (k: string, v: number) => {
    try {
      await patch.mutateAsync({ strategy: { [k]: v } });
    } catch (e: unknown) {
      const detail = (e as { detail?: { detail?: string } | string })?.detail ?? String(e);
      const msg = typeof detail === 'string' ? detail : detail?.detail ?? 'Failed';
      Alert.alert('Update failed', msg);
    }
  };

  return (
    <SafeAreaView style={styles.bg} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: space(4) }}>
        <Text style={text.h2}>Settings</Text>

        {/* Mode */}
        <Text style={styles.section}>MODE</Text>
        <View style={styles.row}>
          <Text style={text.body}>Active mode</Text>
          <ModeChip mode={health?.mode ?? null} onPress={() => setShowModeSheet(true)} />
        </View>

        {/* API keys */}
        <Text style={styles.section}>EXCHANGE API KEYS</Text>
        <View style={styles.warn}>
          <Text style={{ color: colors.red, fontWeight: '700', marginBottom: 2 }}>
            Crypto API keys are dangerous credentials
          </Text>
          <Text style={text.muted}>
            Use trading-only keys (no withdraw). IP-allowlist your server. The mobile app is for
            personal use; do not expose this API to the internet without TLS + reverse proxy.
          </Text>
        </View>
        {(creds ?? []).map((c) => (
          <View key={c.id} style={styles.credRow}>
            <View style={{ flex: 1 }}>
              <Text style={[text.body, { fontWeight: '700' }]}>{c.id}</Text>
              <Text style={text.muted}>
                {c.testnet ? 'testnet' : 'MAINNET'} ·{' '}
                {c.last_verified_at ? `verified` : 'not verified'}
                {c.label ? ` · ${c.label}` : ''}
              </Text>
            </View>
            <Pressable
              onPress={() => verify.mutate(c.id)}
              style={[styles.btnSm, { borderColor: colors.accent }]}
            >
              <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 11 }}>VERIFY</Text>
            </Pressable>
            <Pressable
              onPress={() =>
                Alert.alert('Delete?', `Remove credential for ${c.id}?`, [
                  { text: 'Cancel', style: 'cancel' },
                  { text: 'Delete', style: 'destructive', onPress: () => del.mutate(c.id) },
                ])
              }
              style={[styles.btnSm, { borderColor: colors.red, marginLeft: space(2) }]}
            >
              <Text style={{ color: colors.red, fontWeight: '700', fontSize: 11 }}>RM</Text>
            </Pressable>
          </View>
        ))}
        <Pressable
          onPress={() => setShowCredForm(true)}
          style={[styles.btn, { borderColor: colors.accent }]}
        >
          <Text style={{ color: colors.accent, fontWeight: '700' }}>Add API key</Text>
        </Pressable>

        {/* Risk */}
        <Text style={styles.section}>RISK</Text>
        {lockMainnet && (
          <Text style={[text.muted, { color: colors.amber, marginBottom: space(2) }]}>
            Stop the bot before changing risk on mainnet.
          </Text>
        )}
        {RISK_FIELDS.map((f) => (
          <NumField
            key={f.key}
            label={f.label}
            value={Number(cfg?.risk?.[f.key] ?? 0)}
            disabled={!!lockMainnet}
            onCommit={(v) => updateRisk(f.key, v)}
            step={f.step}
            min={f.min}
            max={f.max}
          />
        ))}

        <Text style={styles.section}>STRATEGY</Text>
        {STRAT_FIELDS.map((f) => (
          <NumField
            key={f.key}
            label={f.label}
            value={Number(cfg?.strategy?.[f.key] ?? 0)}
            disabled={!!lockMainnet}
            onCommit={(v) => updateStrat(f.key, v)}
            step={f.step}
            min={f.min}
            max={f.max}
          />
        ))}

        <Text style={styles.section}>API CONNECTION</Text>
        <View style={styles.row}>
          <Text style={text.body}>Server</Text>
          <Text style={text.muted}>
            {process.env.EXPO_PUBLIC_API_URL ?? '127.0.0.1:8787'}
          </Text>
        </View>
        <View style={styles.row}>
          <Text style={text.body}>Token</Text>
          <Text style={text.muted}>••••••••</Text>
        </View>

        <View style={styles.about}>
          <Text style={{ color: colors.red, fontWeight: '700' }}>Disclaimer</Text>
          <Text style={text.muted}>
            This is not financial advice. Trading bots can and do lose money. Backtest, walk-forward,
            and paper-trade before risking real capital.
          </Text>
        </View>
      </ScrollView>

      <CredentialsForm visible={showCredForm} onClose={() => setShowCredForm(false)} />
      <ModeSwitcherSheet
        visible={showModeSheet}
        current={health?.mode ?? null}
        onClose={() => setShowModeSheet(false)}
      />
    </SafeAreaView>
  );
};

type NumFieldProps = {
  label: string;
  value: number;
  step: number;
  min: number;
  max: number;
  disabled: boolean;
  onCommit: (v: number) => void;
};

const NumField: React.FC<NumFieldProps> = ({ label, value, step, min, max, disabled, onCommit }) => {
  const [draft, setDraft] = useState(String(value));
  const commit = () => {
    const n = Number(draft);
    if (Number.isNaN(n)) return;
    const clamped = Math.max(min, Math.min(max, n));
    onCommit(clamped);
    setDraft(String(clamped));
  };
  React.useEffect(() => {
    setDraft(String(value));
  }, [value]);
  return (
    <View style={[styles.numRow, disabled && { opacity: 0.5 }]}>
      <Text style={text.body}>{label}</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space(2) }}>
        <Pressable
          disabled={disabled}
          onPress={() => onCommit(Math.max(min, value - step))}
          style={styles.stepBtn}
        >
          <Text style={text.body}>−</Text>
        </Pressable>
        <TextInput
          editable={!disabled}
          value={draft}
          onChangeText={setDraft}
          onBlur={commit}
          keyboardType="numeric"
          style={styles.numInput}
        />
        <Pressable
          disabled={disabled}
          onPress={() => onCommit(Math.min(max, value + step))}
          style={styles.stepBtn}
        >
          <Text style={text.body}>+</Text>
        </Pressable>
        <Text style={[text.muted, { width: 50, textAlign: 'right' }]}>{fmtNum(value, 4)}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: colors.bg },
  section: {
    color: colors.muted,
    fontSize: 11,
    letterSpacing: 1.5,
    marginTop: space(5),
    marginBottom: space(2),
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: space(3),
    paddingHorizontal: space(3),
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    marginBottom: space(2),
  },
  warn: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radii.sm,
    padding: space(3),
    borderColor: colors.red,
    borderWidth: 1,
    marginBottom: space(3),
  },
  credRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(3),
    marginBottom: space(2),
  },
  btn: {
    alignItems: 'center',
    paddingVertical: space(3),
    borderRadius: radii.md,
    borderWidth: 1,
    backgroundColor: colors.surface,
  },
  btnSm: {
    paddingHorizontal: space(2),
    paddingVertical: space(1),
    borderRadius: radii.sm,
    borderWidth: 1,
  },
  numRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: space(3),
    paddingHorizontal: space(3),
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    marginBottom: space(2),
  },
  stepBtn: {
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radii.sm,
  },
  numInput: {
    width: 80,
    paddingHorizontal: space(2),
    paddingVertical: space(1),
    color: colors.text,
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceAlt,
    textAlign: 'right',
  },
  about: {
    marginTop: space(6),
    backgroundColor: colors.surfaceAlt,
    borderRadius: radii.md,
    borderColor: colors.red,
    borderWidth: 1,
    padding: space(4),
  },
});
