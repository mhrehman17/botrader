import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { colors, radii, space } from '../theme';
import type { Mode } from '../api/client';

type Props = { mode: Mode | null; onPress?: () => void };

export const ModeChip: React.FC<Props> = ({ mode, onPress }) => {
  const tint =
    mode === 'mainnet' ? colors.mainnet : mode === 'testnet' ? colors.testnet : colors.paper;
  const label = (mode ?? 'OFFLINE').toUpperCase();
  return (
    <Pressable onPress={onPress} style={[styles.chip, { borderColor: tint }]}>
      <Text style={[styles.text, { color: tint }]}>{label}</Text>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: space(3),
    paddingVertical: space(1),
    borderRadius: radii.pill,
    borderWidth: 1,
    backgroundColor: colors.surface,
  },
  text: { fontSize: 11, fontWeight: '700', letterSpacing: 1.5 },
});
