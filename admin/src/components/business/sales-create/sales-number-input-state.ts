export function parseSalesNumberDraft(draft: string, minimum: number) {
  if (!draft.trim()) return null;
  const value = Number(draft);
  if (!Number.isFinite(value) || value < minimum) return null;
  return value;
}

export function commitSalesNumberDraft(draft: string, previousValue: number, minimum: number) {
  return parseSalesNumberDraft(draft, minimum) ?? Math.max(minimum, previousValue || minimum);
}
