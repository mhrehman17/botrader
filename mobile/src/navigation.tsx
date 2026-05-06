import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { Text } from 'react-native';
import { ChartScreen } from './screens/ChartScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { HistoryScreen } from './screens/HistoryScreen';
import { PositionsScreen } from './screens/PositionsScreen';
import { ScannerScreen } from './screens/ScannerScreen';
import { SettingsScreen } from './screens/SettingsScreen';
import { colors } from './theme';

const Tabs = createBottomTabNavigator();

const tabIcon = (label: string) => ({
  tabBarIcon: ({ focused }: { focused: boolean }) => (
    <Text
      style={{
        fontSize: 10,
        color: focused ? colors.accent : colors.muted,
        fontWeight: '700',
        letterSpacing: 1,
      }}
    >
      {label}
    </Text>
  ),
});

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.bg,
    card: colors.surface,
    text: colors.text,
    border: colors.border,
    primary: colors.accent,
  },
};

export const RootNav: React.FC = () => (
  <NavigationContainer theme={navTheme}>
    <Tabs.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: '700' },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="Dashboard" component={DashboardScreen} options={tabIcon('DASH')} />
      <Tabs.Screen name="Positions" component={PositionsScreen} options={tabIcon('POS')} />
      <Tabs.Screen name="Scanner" component={ScannerScreen} options={tabIcon('SCAN')} />
      <Tabs.Screen name="Chart" component={ChartScreen} options={tabIcon('CHART')} />
      <Tabs.Screen name="History" component={HistoryScreen} options={tabIcon('HIST')} />
      <Tabs.Screen name="Settings" component={SettingsScreen} options={tabIcon('CFG')} />
    </Tabs.Navigator>
  </NavigationContainer>
);
