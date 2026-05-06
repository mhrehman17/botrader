import React from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ScannerRow } from '../components/ScannerRow';
import { useScan } from '../api/hooks';
import { colors, space, text } from '../theme';

export const ScannerScreen: React.FC = () => {
  const { data: rows, isFetching, refetch } = useScan();
  return (
    <SafeAreaView style={styles.bg} edges={['top']}>
      <View style={styles.header}>
        <Text style={text.h2}>Scanner</Text>
        <Text style={text.muted}>HTF bias and LTF state per symbol</Text>
      </View>
      <FlatList
        data={rows ?? []}
        keyExtractor={(r) => r.symbol}
        contentContainerStyle={{ padding: space(4) }}
        renderItem={({ item }) => <ScannerRow r={item} />}
        refreshControl={
          <RefreshControl tintColor={colors.muted} refreshing={isFetching} onRefresh={refetch} />
        }
        ListEmptyComponent={
          <Text style={[text.muted, { textAlign: 'center', marginTop: space(8) }]}>
            No symbols scanning. Start the bot.
          </Text>
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: space(4), paddingTop: space(2), paddingBottom: space(3) },
});
