import React from 'react';
import { Text, View, StyleSheet } from 'react-native';
import { colors, radii, space, text } from '../theme';

type Props = { label: string; value: string; tone?: 'pos' | 'neg' | 'neutral' };

export const StatPill: React.FC<Props> = ({ label, value, tone = 'neutral' }) => {
  const tint =
    tone === 'pos' ? colors.green : tone === 'neg' ? colors.red : colors.text;
  return (
    <View style={styles.box}>
      <Text style={text.muted}>{label}</Text>
      <Text style={[text.mono, { color: tint, marginTop: 2 }]}>{value}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  box: {
    flex: 1,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(3),
    marginRight: space(2),
  },
});
