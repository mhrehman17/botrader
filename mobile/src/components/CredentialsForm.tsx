import React, { useState } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useUpsertCredential, useVerifyCredential } from '../api/hooks';
import { colors, radii, space, text } from '../theme';

const COMMON_EXCHANGES = ['binanceusdm', 'bybit', 'okx', 'kucoinfutures', 'bitget'];

type Props = { visible: boolean; onClose: () => void; defaultExchange?: string };

export const CredentialsForm: React.FC<Props> = ({ visible, onClose, defaultExchange }) => {
  const upsert = useUpsertCredential();
  const verify = useVerifyCredential();
  const [exchangeId, setExchangeId] = useState(defaultExchange ?? 'binanceusdm');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [testnet, setTestnet] = useState(true);
  const [label, setLabel] = useState('');
  const [busy, setBusy] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);

  const reset = () => {
    setApiKey('');
    setApiSecret('');
    setLabel('');
    setVerifyMsg(null);
  };

  const submit = async () => {
    if (!apiKey || !apiSecret) {
      Alert.alert('Missing', 'API key and secret are required.');
      return;
    }
    setBusy(true);
    try {
      await upsert.mutateAsync({
        exchange_id: exchangeId,
        api_key: apiKey,
        api_secret: apiSecret,
        testnet,
        label,
      });
      reset();
      onClose();
    } catch (e: unknown) {
      const detail = (e as { detail?: { detail?: string } | string })?.detail ?? String(e);
      const msg = typeof detail === 'string' ? detail : detail?.detail ?? 'Failed';
      Alert.alert('Save failed', msg);
    } finally {
      setBusy(false);
    }
  };

  const tryVerify = async () => {
    setBusy(true);
    setVerifyMsg(null);
    try {
      const res = (await verify.mutateAsync(exchangeId)) as {
        ok: boolean;
        error?: string;
        account_type?: string;
      };
      setVerifyMsg(res.ok ? `OK · ${res.account_type ?? ''}` : `FAIL · ${res.error}`);
    } catch (e: unknown) {
      setVerifyMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <Text style={text.h2}>Exchange API key</Text>

        <View style={styles.warn}>
          <Text style={{ color: colors.amber, fontWeight: '700', marginBottom: 2 }}>
            Use a trading-only key
          </Text>
          <Text style={text.muted}>
            Disable withdraw permission. IP-allowlist your server IP. The server stores secrets
            encrypted at rest.
          </Text>
        </View>

        <Text style={[text.muted, styles.label]}>Exchange</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
          {COMMON_EXCHANGES.map((id) => (
            <Pressable
              key={id}
              onPress={() => setExchangeId(id)}
              style={[
                styles.exChip,
                { borderColor: id === exchangeId ? colors.accent : colors.border },
              ]}
            >
              <Text
                style={{
                  color: id === exchangeId ? colors.accent : colors.muted,
                  fontSize: 12,
                  fontWeight: '700',
                }}
              >
                {id}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={[text.muted, styles.label]}>API key</Text>
        <TextInput
          value={apiKey}
          onChangeText={setApiKey}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="API key"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />

        <Text style={[text.muted, styles.label]}>API secret</Text>
        <TextInput
          value={apiSecret}
          onChangeText={setApiSecret}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="API secret (write-only)"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />

        <Text style={[text.muted, styles.label]}>Label (optional)</Text>
        <TextInput
          value={label}
          onChangeText={setLabel}
          placeholder="e.g. trading-only key"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />

        <View style={styles.tnRow}>
          <Text style={text.body}>Testnet</Text>
          <Switch value={testnet} onValueChange={setTestnet} />
        </View>

        {verifyMsg && (
          <Text
            style={{
              color: verifyMsg.startsWith('OK') ? colors.green : colors.red,
              marginTop: space(2),
            }}
          >
            {verifyMsg}
          </Text>
        )}

        <View style={styles.actions}>
          <Pressable
            onPress={tryVerify}
            disabled={busy}
            style={[styles.btn, { borderColor: colors.accent }]}
          >
            <Text style={{ color: colors.accent, fontWeight: '700' }}>Verify</Text>
          </Pressable>
          <Pressable
            onPress={submit}
            disabled={busy}
            style={[styles.btn, { backgroundColor: colors.accent, borderColor: colors.accent }]}
          >
            <Text style={{ color: '#0a0a0c', fontWeight: '700' }}>Save</Text>
          </Pressable>
        </View>

        <Pressable style={{ alignItems: 'center', marginTop: space(3) }} onPress={onClose}>
          <Text style={text.muted}>Close</Text>
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
  warn: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radii.sm,
    padding: space(3),
    marginTop: space(2),
    borderColor: colors.amber,
    borderWidth: 1,
  },
  label: { marginTop: space(3), marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2),
    color: colors.text,
  },
  exChip: {
    paddingHorizontal: space(3),
    paddingVertical: space(1),
    borderRadius: radii.pill,
    borderWidth: 1,
    backgroundColor: colors.surfaceAlt,
    marginRight: space(2),
    marginBottom: space(2),
  },
  tnRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space(3),
  },
  actions: { flexDirection: 'row', gap: space(2), marginTop: space(4) },
  btn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space(3),
    borderRadius: radii.md,
    borderWidth: 1,
    marginRight: space(2),
  },
});
