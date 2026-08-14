import { Tabs } from "expo-router";

import { colors, typography } from "@/theme/tokens";
import { tabIcon } from "@/utils/tabIcon";

export default function CaregiverLayout() {
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
        options={{ title: "Inicio", tabBarIcon: tabIcon("home") }}
      />
      <Tabs.Screen
        name="route"
        options={{ title: "Mi ruta", tabBarIcon: tabIcon("map") }}
      />
      <Tabs.Screen
        name="assistant"
        options={{ title: "Kinti", tabBarIcon: tabIcon("chatbubble-ellipses") }}
      />
      <Tabs.Screen
        name="companion"
        options={{ title: "Su espacio", tabBarIcon: tabIcon("happy") }}
      />
      <Tabs.Screen
        name="help"
        options={{ title: "Ayuda", tabBarIcon: tabIcon("help-buoy") }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: "Perfil", tabBarIcon: tabIcon("person") }}
      />
    </Tabs>
  );
}
