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
      {/* Oculta de la barra por ahora, junto con el resto del acceso al
          espacio del paciente. La ruta y la pantalla siguen intactas. */}
      <Tabs.Screen
        name="companion"
        options={{ title: "Su espacio", tabBarIcon: tabIcon("happy"), href: null }}
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
