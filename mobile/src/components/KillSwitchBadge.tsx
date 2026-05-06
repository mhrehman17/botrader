import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useKillSwitch } from '../api/hooks';
import { colors, radii, space } from '../theme';

export const KillSwitchBadge: React.FC = () => {
  const { data } = useKillSwitch();
  if (!data?.tripped) return null;
  return (
    <View style={styles.box}>
      <Text style={styles.text}>KILL: {data.reason}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  box: {
    backgroundColor: colors.red,
    paddingHorizontal: space(3),
    paddingVertical: space(1),
    borderRadius: radii.sm,
  },
  text: { color: '#fff', fontWeight: '700', fontSize: 11, letterSpacing: 1 },
});
