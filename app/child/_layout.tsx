import { Tabs } from "expo-router";

import { colors, typography } from "@/theme/tokens";
import { tabIcon } from "@/utils/tabIcon";

export default function ChildLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accentDark,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarLabelStyle: typography.caption,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Mi espacio", tabBarIcon: tabIcon("home") }}
      />
      <Tabs.Screen
        name="feelings"
        options={{ title: "Cómo me siento", tabBarIcon: tabIcon("happy") }}
      />
      <Tabs.Screen
        name="support"
        options={{ title: "Quiero decir algo", tabBarIcon: tabIcon("hand-left") }}
      />
      <Tabs.Screen
        name="exit"
        options={{ title: "Para mi adulto", tabBarIcon: tabIcon("lock-closed") }}
      />
      {/* El detalle de una actividad se abre desde la tarjeta, no desde la barra. */}
      <Tabs.Screen name="activity/[key]" options={{ href: null }} />
    </Tabs>
  );
}
