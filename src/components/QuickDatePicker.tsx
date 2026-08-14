/**
 * Selección de fecha.
 *
 * Los accesos rápidos siguen siendo el camino principal: botones grandes y sin
 * calendario que interpretar. La fecha libre se abre sólo cuando hace falta, y
 * el servidor la valida igual (no se aceptan fechas pasadas).
 */

import { useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import DateTimePicker, { type DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { formatDateTime } from "@/utils/formatDate";
import { buildQuickDateOptions } from "@/utils/quickDates";

interface QuickDatePickerProps {
  value?: string;
  onSelect: (iso: string) => void;
}

type Stage = "closed" | "date" | "time";

export function QuickDatePicker({ value, onSelect }: QuickDatePickerProps) {
  const options = buildQuickDateOptions();
  const [stage, setStage] = useState<Stage>("closed");
  const [draft, setDraft] = useState<Date>(() => defaultDraft(value));

  const isCustom = value !== undefined && !options.some((option) => option.iso === value);

  function handleDateChange(event: DateTimePickerEvent, picked?: Date) {
    if (event.type === "dismissed" || !picked) {
      setStage("closed");
      return;
    }
    const next = new Date(draft);
    next.setFullYear(picked.getFullYear(), picked.getMonth(), picked.getDate());
    setDraft(next);
    // En Android el selector es modal y la hora se pide en un segundo paso.
    setStage(Platform.OS === "android" ? "time" : "closed");
    if (Platform.OS !== "android") onSelect(next.toISOString());
  }

  function handleTimeChange(event: DateTimePickerEvent, picked?: Date) {
    setStage("closed");
    if (event.type === "dismissed" || !picked) return;
    const next = new Date(draft);
    next.setHours(picked.getHours(), picked.getMinutes(), 0, 0);
    setDraft(next);
    onSelect(next.toISOString());
  }

  return (
    <View style={styles.wrapper}>
      <View style={styles.grid}>
        {options.map((option) => {
          const selected = value === option.iso;
          return (
            <Pressable
              key={option.iso}
              onPress={() => onSelect(option.iso)}
              accessibilityRole="button"
              accessibilityLabel={`Reprogramar para ${option.label}`}
              accessibilityState={{ selected }}
              style={[styles.option, selected && styles.optionSelected]}
            >
              <Text style={[styles.optionText, selected && styles.optionTextSelected]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}

        <Pressable
          onPress={() => setStage("date")}
          accessibilityRole="button"
          accessibilityLabel="Elegir otra fecha y hora"
          accessibilityState={{ selected: isCustom }}
          style={[styles.option, styles.customOption, isCustom && styles.optionSelected]}
        >
          <Ionicons
            name="calendar-outline"
            size={16}
            color={isCustom ? colors.textInverse : colors.primaryDark}
          />
          <Text style={[styles.optionText, isCustom && styles.optionTextSelected]}>
            Otra fecha
          </Text>
        </Pressable>
      </View>

      {isCustom ? (
        <Text style={styles.customValue}>Fecha elegida: {formatDateTime(value)}</Text>
      ) : null}

      {stage === "date" ? (
        <DateTimePicker
          value={draft}
          mode="date"
          minimumDate={new Date()}
          onChange={handleDateChange}
        />
      ) : null}
      {stage === "time" ? (
        <DateTimePicker value={draft} mode="time" onChange={handleTimeChange} />
      ) : null}
    </View>
  );
}

function defaultDraft(value?: string): Date {
  if (value) return new Date(value);
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(9, 0, 0, 0);
  return tomorrow;
}

const styles = StyleSheet.create({
  wrapper: {
    gap: spacing.sm,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  option: {
    minHeight: touchTarget.minHeight,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  customOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderColor: colors.primary,
  },
  optionSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  optionText: {
    ...typography.caption,
    color: colors.textPrimary,
  },
  optionTextSelected: {
    color: colors.textInverse,
  },
  customValue: {
    ...typography.caption,
    color: colors.textSecondary,
  },
});
