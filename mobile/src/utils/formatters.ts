/**
 * Formatting utilities for Munim-AI facts and currency.
 *
 * All logic strictly follows backend definitions from:
 * backend/app/services/insights.py & docs/contracts/backend-api-v0.md
 */

import { InsightFact } from '@/api/ledgerClient';

/**
 * Format a fact's current value based on its unit and id.
 */
export function formatFactValue(fact: InsightFact): string {
  if (fact.value === null || fact.value === undefined) {
    return '(Unavailable)';
  }

  const numVal = typeof fact.value === 'number' ? fact.value : parseFloat(String(fact.value));

  if (!isNaN(numVal)) {
    if (fact.unit === 'INR') {
      return `₹${numVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    if (fact.unit === 'INR_paise') {
      return `₹${(numVal / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    if (fact.unit === 'percent') {
      const sign = numVal > 0 ? '+' : '';
      return `${sign}${numVal.toFixed(1)}%`;
    }
    if (fact.unit === 'payer_tokens') {
      return `${numVal} tokens`;
    }
    return `${numVal} ${fact.unit ?? ''}`.trim();
  }

  return String(fact.value);
}

/**
 * Format a fact's comparison value.
 *
 * NOTE: For `collection_change_pct`, the backend provides `comparison_value`
 * as the baseline collections in RUPEES (`baseline_total / 100`), NOT as a percentage!
 * For `payment_collections`, it is also baseline collections in RUPEES.
 * For `median_ticket`, it is baseline median ticket in RUPEES.
 */
export function formatComparisonValue(fact: InsightFact): string | null {
  if (fact.comparison_value === null || fact.comparison_value === undefined) {
    return null;
  }

  const numVal = typeof fact.comparison_value === 'number'
    ? fact.comparison_value
    : parseFloat(String(fact.comparison_value));

  if (isNaN(numVal)) {
    return String(fact.comparison_value);
  }

  // collection_change_pct comparison_value is baseline collections in Rupees!
  if (fact.id === 'collection_change_pct') {
    return `Baseline collections: ₹${numVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  if (fact.unit === 'INR' || fact.id === 'payment_collections' || fact.id === 'median_ticket') {
    return `Prev window: ₹${numVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  if (fact.unit === 'percent') {
    return `Prev window: ${numVal.toFixed(1)}%`;
  }

  return `Prev window: ${numVal} ${fact.unit ?? ''}`.trim();
}

