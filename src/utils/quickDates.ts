export interface QuickDateOption {
  label: string;
  iso: string;
}

export function buildQuickDateOptions(now: Date = new Date()): QuickDateOption[] {
  const offsets: { label: string; days: number }[] = [
    { label: "Mañana, 9:00 a. m.", days: 1 },
    { label: "En 3 días, 9:00 a. m.", days: 3 },
    { label: "En 7 días, 9:00 a. m.", days: 7 },
    { label: "En 14 días, 9:00 a. m.", days: 14 },
  ];

  return offsets.map(({ label, days }) => {
    const date = new Date(now);
    date.setDate(date.getDate() + days);
    date.setHours(9, 0, 0, 0);
    return { label, iso: date.toISOString() };
  });
}
