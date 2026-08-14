import type { ColorValue } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import type { IconName } from "@/theme/statusPresentation";

export function tabIcon(name: IconName) {
  return function TabBarIcon({ color, size }: { focused: boolean; color: ColorValue; size: number }) {
    return <Ionicons name={name} size={size} color={color as string} />;
  };
}
