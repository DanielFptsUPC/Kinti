import { Stack } from "expo-router";

import { colors } from "@/theme/tokens";

export default function PatientsStackLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.textPrimary,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Pacientes" }} />
      <Stack.Screen name="[id]" options={{ title: "Detalle del paciente" }} />
      <Stack.Screen name="new-milestone" options={{ title: "Registrar hito", presentation: "modal" }} />
    </Stack>
  );
}
