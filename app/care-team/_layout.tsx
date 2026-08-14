import { Tabs } from "expo-router";

import { colors, typography } from "@/theme/tokens";
import { tabIcon } from "@/utils/tabIcon";

export default function CareTeamLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primaryDark,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarLabelStyle: typography.caption,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Resumen", tabBarIcon: tabIcon("stats-chart") }}
      />
      <Tabs.Screen
        name="patients"
        options={{ title: "Pacientes", tabBarIcon: tabIcon("people") }}
      />
      <Tabs.Screen
        name="alerts"
        options={{ title: "Alertas", tabBarIcon: tabIcon("warning") }}
      />
      <Tabs.Screen
        name="operations"
        options={{ title: "Coordinar", tabBarIcon: tabIcon("git-compare") }}
      />
    </Tabs>
  );
}
