import React, { useMemo, useState } from 'react';
import {
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Line, Rect } from 'react-native-svg';
import { useCandles, useScan } from '../api/hooks';
import { colors, radii, space, text } from '../theme';
import { fmtNum } from '../utils/format';

export const ChartScreen: React.FC = () => {
  const { data: scan } = useScan();
  const symbols = scan?.map((r) => r.symbol) ?? ['BTC/USDT:USDT'];
  const [symbol, setSymbol] = useState<string>(symbols[0] ?? 'BTC/USDT:USDT');
  const [showOB, setShowOB] = useState(true);
  const [showFVG, setShowFVG] = useState(true);
  const [showSweeps, setShowSweeps] = useState(true);

  const { data: bars } = useCandles(symbol, '5m', 200);

  const view = useMemo(() => {
    if (!bars?.candles?.length) return null;
    const w = Dimensions.get('window').width - 32;
    const h = 320;
    const candles = bars.candles;
    const lows = candles.map((c) => c.low);
    const highs = candles.map((c) => c.high);
    const minY = Math.min(...lows);
    const maxY = Math.max(...highs);
    const range = maxY - minY || 1;
    const cw = Math.max(1, w / candles.length);
    const sx = (i: number) => i * cw;
    const sy = (y: number) => h - ((y - minY) / range) * h;

    return { w, h, candles, sx, sy, cw, minY, maxY, range };
  }, [bars]);

  return (
    <SafeAreaView style={styles.bg} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: space(4) }}>
        <Text style={text.h2}>Chart</Text>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.symRow}>
          {symbols.map((s) => (
            <Pressable
              key={s}
              onPress={() => setSymbol(s)}
              style={[styles.chip, { borderColor: symbol === s ? colors.accent : colors.border }]}
            >
              <Text
                style={{
                  color: symbol === s ? colors.accent : colors.muted,
                  fontSize: 12,
                  fontWeight: '700',
                }}
              >
                {s}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        {view ? (
          <View style={styles.chartCard}>
            <Svg width={view.w} height={view.h}>
              {/* Order Blocks */}
              {showOB &&
                bars!.overlays.order_blocks.map((ob, i) => {
                  const x = view.sx(ob.idx);
                  const y1 = view.sy(ob.top);
                  const y2 = view.sy(ob.bottom);
                  const tint = ob.side === 'long' ? colors.green : colors.red;
                  return (
                    <Rect
                      key={`ob-${i}`}
                      x={x}
                      y={Math.min(y1, y2)}
                      width={view.w - x}
                      height={Math.abs(y2 - y1)}
                      fill={tint}
                      opacity={ob.mitigated ? 0.05 : 0.12}
                    />
                  );
                })}

              {/* FVGs */}
              {showFVG &&
                bars!.overlays.fvgs.map((g, i) => {
                  const x = view.sx(g.idx);
                  const y1 = view.sy(g.top);
                  const y2 = view.sy(g.bottom);
                  const tint = g.side === 'long' ? colors.accent : colors.amber;
                  return (
                    <Rect
                      key={`fvg-${i}`}
                      x={x}
                      y={Math.min(y1, y2)}
                      width={view.w - x}
                      height={Math.abs(y2 - y1)}
                      fill={tint}
                      opacity={g.filled ? 0.05 : 0.18}
                    />
                  );
                })}

              {/* Sweeps */}
              {showSweeps &&
                bars!.overlays.sweeps.map((s, i) => {
                  const x = view.sx(s.idx);
                  const y = view.sy(s.extreme);
                  return (
                    <Line
                      key={`sw-${i}`}
                      x1={x - 2}
                      x2={x + view.cw + 2}
                      y1={y}
                      y2={y}
                      stroke={s.is_high ? colors.red : colors.green}
                      strokeWidth={1.5}
                      strokeDasharray="3,3"
                    />
                  );
                })}

              {/* Candles last so they paint on top */}
              {view.candles.map((c, i) => {
                const x = view.sx(i);
                const yh = view.sy(c.high);
                const yl = view.sy(c.low);
                const yo = view.sy(c.open);
                const yc = view.sy(c.close);
                const bullish = c.close >= c.open;
                const tint = bullish ? colors.green : colors.red;
                const bodyTop = Math.min(yo, yc);
                const bodyH = Math.max(1, Math.abs(yo - yc));
                return (
                  <React.Fragment key={i}>
                    <Line x1={x + view.cw / 2} x2={x + view.cw / 2} y1={yh} y2={yl} stroke={tint} strokeWidth={1} />
                    <Rect
                      x={x + 0.5}
                      y={bodyTop}
                      width={Math.max(1, view.cw - 1)}
                      height={bodyH}
                      fill={tint}
                    />
                  </React.Fragment>
                );
              })}
            </Svg>

            <View style={styles.legend}>
              <Text style={text.muted}>
                {fmtNum(view.minY, 2)} – {fmtNum(view.maxY, 2)}
              </Text>
              <Text style={text.muted}>{view.candles.length} bars · 5m</Text>
            </View>
          </View>
        ) : (
          <Text style={[text.muted, { textAlign: 'center', marginTop: space(8) }]}>
            Waiting for bars… start the bot.
          </Text>
        )}

        <View style={styles.toggles}>
          <View style={styles.toggleRow}>
            <Text style={text.body}>Order Blocks</Text>
            <Switch value={showOB} onValueChange={setShowOB} />
          </View>
          <View style={styles.toggleRow}>
            <Text style={text.body}>Fair Value Gaps</Text>
            <Switch value={showFVG} onValueChange={setShowFVG} />
          </View>
          <View style={styles.toggleRow}>
            <Text style={text.body}>Sweeps</Text>
            <Switch value={showSweeps} onValueChange={setShowSweeps} />
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: colors.bg },
  symRow: { paddingVertical: space(3), gap: space(2) },
  chip: {
    paddingHorizontal: space(3),
    paddingVertical: space(1),
    borderRadius: radii.pill,
    borderWidth: 1,
    backgroundColor: colors.surface,
    marginRight: space(2),
  },
  chartCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.lg,
    padding: space(2),
    marginTop: space(2),
  },
  legend: { flexDirection: 'row', justifyContent: 'space-between', marginTop: space(2) },
  toggles: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.md,
    padding: space(3),
    marginTop: space(4),
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: space(2),
  },
});
