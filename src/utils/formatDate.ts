export function formatDateTime(iso?: string): string {
  if (!iso) return "Fecha por definir";
  const date = new Date(iso);
  const datePart = date.toLocaleDateString("es-PE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  const timePart = date.toLocaleTimeString("es-PE", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${capitalize(datePart)} · ${timePart}`;
}

export function formatDate(iso?: string): string {
  if (!iso) return "Fecha por definir";
  const date = new Date(iso);
  return capitalize(
    date.toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric" }),
  );
}

export function formatRelativeToNow(iso?: string, now: Date = new Date()): string {
  if (!iso) return "";
  const diffMs = new Date(iso).getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Hoy";
  if (diffDays === 1) return "Mañana";
  if (diffDays === -1) return "Ayer";
  if (diffDays > 1) return `En ${diffDays} días`;
  return `Hace ${Math.abs(diffDays)} días`;
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
