import React, { useState } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import type { Mode } from '../api/client';
import { useServerInfo, useSwitchMode } from '../api/hooks';
import { colors, radii, space, text } from '../theme';

type Props = { visible: boolean; current: Mode | null; onClose: () => void };

const modes: { id: Mode; label: string; tint: string; description: string }[] = [
  { id: 'paper', label: 'Paper', tint: colors.paper, description: 'Simulated. Safe.' },
  { id: 'testnet', label: 'Testnet', tint: colors.testnet, description: 'Live broker, fake funds.' },
  { id: 'mainnet', label: 'Mainnet', tint: colors.mainnet, description: 'Real funds. Risk of loss.' },
];

export const ModeSwitcherSheet: React.FC<Props> = ({ visible, current, onClose }) => {
  const { data: server } = useServerInfo();
  const switchMode = useSwitchMode();
  const [confirm, setConfirm] = useState('');
  const [pending, setPending] = useState<Mode | null>(null);
  const [error, setError] = useState<string | null>(null);

  const allowMainnet = !!server?.allow_mainnet;

  const submit = async (target: Mode) => {
    setError(null);
    if (target === current) {
      onClose();
      return;
    }
    if (target === 'mainnet' && !allowMainnet) {
      setError('Server is not started with BOTRADER_ALLOW_MAINNET=1.');
      return;
    }
    if (target === 'mainnet' && confirm !== 'MAINNET') {
      setError('Type MAINNET to confirm switching to real funds.');
      return;
    }
    setPending(target);
    try {
      await switchMode.mutateAsync({
        mode: target,
        confirm: target === 'mainnet' ? 'MAINNET' : undefined,
      });
      setConfirm('');
      onClose();
    } catch (e: unknown) {
      const detail =
        (e as { detail?: { detail?: string } | string })?.detail ?? String(e);
      const msg = typeof detail === 'string' ? detail : detail?.detail ?? 'Failed';
      setError(msg);
      Alert.alert('Mode switch failed', msg);
    } finally {
      setPending(null);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <Text style={text.h2}>Switch mode</Text>
        <Text style={[text.muted, { marginTop: 4, marginBottom: space(3) }]}>
          The bot will stop, swap brokers, and (if previously running) restart.
        </Text>

        {modes.map((m) => {
          const disabled = m.id === 'mainnet' && !allowMainnet;
          const active = current === m.id;
          return (
            <Pressable
              key={m.id}
              disabled={disabled || pending !== null}
              onPress={() => submit(m.id)}
              style={[
                styles.option,
                { borderColor: active ? m.tint : colors.border },
                disabled && { opacity: 0.4 },
              ]}
            >
              <View style={{ flex: 1 }}>
                <Text style={[styles.optionLabel, { color: m.tint }]}>{m.label}</Text>
                <Text style={text.muted}>{m.description}</Text>
                {disabled && (
                  <Text style={[text.muted, { color: colors.red, marginTop: 2 }]}>
                    Disabled — set BOTRADER_ALLOW_MAINNET=1 on the server.
                  </Text>
                )}
              </View>
              {active && <Text style={{ color: m.tint, fontWeight: '700' }}>ACTIVE</Text>}
            </Pressable>
          );
        })}

        <View style={{ marginTop: space(3) }}>
          <Text style={text.muted}>To switch to MAINNET, type MAINNET below:</Text>
          <TextInput
            value={confirm}
            onChangeText={setConfirm}
            autoCapitalize="characters"
            placeholder="MAINNET"
            placeholderTextColor={colors.muted}
            style={styles.input}
          />
        </View>

        {error && <Text style={[text.body, { color: colors.red, marginTop: space(2) }]}>{error}</Text>}
        {pending && (
          <Text style={[text.muted, { marginTop: space(2) }]}>
            Switching to {pending}…
          </Text>
        )}

        <Pressable style={styles.cancel} onPress={onClose}>
          <Text style={text.body}>Close</Text>
        </Pressable>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)' },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    padding: space(5),
    paddingBottom: space(8),
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(3),
    marginBottom: space(2),
  },
  optionLabel: { fontSize: 16, fontWeight: '700', letterSpacing: 1, marginBottom: 2 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2),
    color: colors.text,
    marginTop: space(1),
  },
  cancel: { alignItems: 'center', marginTop: space(4) },
});
