import { InsightFact } from '@/api/ledgerClient';

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

function formatCurrency(value: number): string {
  return inrFormatter.format(value);
}

export function formatFactValue(fact: InsightFact): string {
  if (fact.value === null || fact.value === undefined) return 'Unavailable';
  if (fact.unit === 'INR' && typeof fact.value === 'number') return formatCurrency(fact.value);
  if (fact.unit === 'percent' && typeof fact.value === 'number') return `${fact.value.toFixed(1)}%`;
  if (fact.unit === 'payer_tokens') return `${fact.value} payer tokens`;
  return fact.unit ? `${fact.value} ${fact.unit}` : String(fact.value);
}

export function formatFactComparison(fact: InsightFact): string | null {
  if (fact.comparison_value === null || fact.comparison_value === undefined) return null;
  const period = fact.comparison_period ? ` (${fact.comparison_period})` : '';

  // This fact compares a percent change with the baseline collections amount.
  if (fact.id === 'collection_change_pct' && typeof fact.comparison_value === 'number') {
    return `Baseline collections: ${formatCurrency(fact.comparison_value)}${period}`;
  }

  const previous: InsightFact = { ...fact, value: fact.comparison_value };
  return `Previous period: ${formatFactValue(previous)}${period}`;
}

export function formatFactDefinition(fact: InsightFact): string | null {
  return fact.definition?.trim() || null;
}

export function formatPeriodDate(isoDate: string, timezone: string, exclusiveEnd = false): string {
  const date = new Date(isoDate);
  if (exclusiveEnd) date.setTime(date.getTime() - 1);
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: timezone,
  }).format(date);
}
