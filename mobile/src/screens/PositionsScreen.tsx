import React from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { PositionRow } from '../components/PositionRow';
import { usePositions } from '../api/hooks';
import { colors, space, text } from '../theme';

export const PositionsScreen: React.FC = () => {
  const { data: positions, isFetching, refetch } = usePositions();

  return (
    <SafeAreaView style={styles.bg} edges={['top']}>
      <View style={styles.header}>
        <Text style={text.h2}>Positions</Text>
        <Text style={text.muted}>{positions?.length ?? 0} open</Text>
      </View>
      <FlatList
        data={positions ?? []}
        keyExtractor={(p) => p.symbol}
        contentContainerStyle={{ padding: space(4) }}
        renderItem={({ item }) => <PositionRow p={item} />}
        refreshControl={
          <RefreshControl
            tintColor={colors.muted}
            refreshing={isFetching}
            onRefresh={refetch}
          />
        }
        ListEmptyComponent={
          <Text style={[text.muted, { textAlign: 'center', marginTop: space(8) }]}>
            No open positions.
          </Text>
        }
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
    paddingHorizontal: space(4),
    paddingTop: space(2),
  },
});
