import React from 'react';
import { Dimensions, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import type { EquityPoint } from '../api/client';
import { colors } from '../theme';

type Props = { data: EquityPoint[]; height?: number };

export const EquityChart: React.FC<Props> = ({ data, height = 90 }) => {
  const width = Dimensions.get('window').width - 32;
  if (data.length < 2) {
    return <View style={{ height, width }} />;
  }
  const xs = data.map((_, i) => i);
  const ys = data.map((p) => p.equity);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const sx = (i: number) => (i / (xs.length - 1)) * width;
  const sy = (y: number) =>
    maxY === minY ? height / 2 : height - ((y - minY) / (maxY - minY)) * height;
  const d = ys.map((y, i) => `${i === 0 ? 'M' : 'L'} ${sx(i).toFixed(1)} ${sy(y).toFixed(1)}`).join(' ');
  const stroke = ys[ys.length - 1] >= ys[0] ? colors.green : colors.red;
  return (
    <Svg width={width} height={height}>
      <Path d={d} stroke={stroke} strokeWidth={1.5} fill="none" />
    </Svg>
  );
};
