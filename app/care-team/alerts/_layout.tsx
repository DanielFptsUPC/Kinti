import { Stack } from "expo-router";

import { colors } from "@/theme/tokens";

export default function AlertsStackLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.textPrimary,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Alertas" }} />
      <Stack.Screen name="[id]" options={{ title: "Gestionar alerta" }} />
    </Stack>
  );
}
