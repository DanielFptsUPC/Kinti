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
        options={{ title: "Mi aventura", tabBarIcon: tabIcon("planet") }}
      />
      <Tabs.Screen
        name="feelings"
        options={{ title: "Cómo me siento", tabBarIcon: tabIcon("happy") }}
      />
    </Tabs>
  );
}
