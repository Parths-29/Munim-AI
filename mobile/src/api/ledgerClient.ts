/**
 * Typed client for KiranaOS Backend API v0.2
 * Ref: docs/contracts/backend-api-v0.md
 *
 * Implements:
 * - GET  /health
 * - POST /customers
 * - GET  /customers/resolve?query=...
 * - GET  /ledger/customers/{customer_id}/balance
 * - POST /ledger/credits
 * - POST /ledger/repayments
 *
 * Explicitly NOT implemented in v0.2:
 * - Stock/product APIs, timeline, payment reconciliation, voice/LLM, insights.
 */

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export interface HealthResponse {
  status: string;
  phase: string;
  data_mode: string;
}

export interface Customer {
  customer_id: string;
  display_name: string;
  aliases: string[];
}

export interface CreateCustomerRequest {
  display_name: string;
  aliases: string[];
  confirmed: boolean;
  idempotency_key: string;
}

export type CustomerResolveStatus = 'RESOLVED' | 'AMBIGUOUS' | 'NOT_FOUND';

export interface CustomerResolveResponse {
  status: CustomerResolveStatus;
  query: string;
  customer?: Customer;
  matches?: Customer[];
}

export interface CustomerBalanceResponse {
  customer_id: string;
  balance_due_paise: number;
  currency: 'INR';
  posted_entries_count: number;
}

export interface LedgerEntryRequest {
  customer_id: string;
  amount_paise: number;
  source_event_id: string;
  idempotency_key: string;
  confirmed: boolean;
}

export interface LedgerEntryResponse {
  entry_id: string;
  shop_id: string;
  customer_id: string;
  type: 'CREDIT' | 'REPAYMENT';
  amount_paise: number;
  source_event_id: string;
  status: 'POSTED';
  created_at: string;
  idempotent_replay?: boolean;
}

/** Check backend health */
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with HTTP ${res.status}`);
  }
  return res.json();
}

/** Resolve a customer alias/query */
export async function resolveCustomer(
  query: string
): Promise<CustomerResolveResponse> {
  const res = await fetch(
    `${API_BASE_URL}/customers/resolve?query=${encodeURIComponent(query)}`
  );
  if (!res.ok) {
    throw new Error(`Customer resolve failed with HTTP ${res.status}`);
  }
  return res.json();
}

/** Create a new customer record */
export async function createCustomer(
  req: CreateCustomerRequest
): Promise<Customer> {
  const res = await fetch(`${API_BASE_URL}/customers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Create customer failed with HTTP ${res.status}`);
  }
  return res.json();
}

/** Get derived balance for a customer */
export async function fetchCustomerBalance(
  customerId: string
): Promise<CustomerBalanceResponse> {
  const res = await fetch(
    `${API_BASE_URL}/ledger/customers/${encodeURIComponent(customerId)}/balance`
  );
  if (!res.ok) {
    throw new Error(`Fetch balance failed with HTTP ${res.status}`);
  }
  return res.json();
}

/** Post a confirmed credit entry */
export async function postCredit(
  req: LedgerEntryRequest
): Promise<LedgerEntryResponse> {
  const res = await fetch(`${API_BASE_URL}/ledger/credits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(
      errorBody?.detail ?? `Credit entry failed with HTTP ${res.status}`
    );
  }
  return res.json();
}

/** Post a confirmed repayment entry */
export async function postRepayment(
  req: LedgerEntryRequest
): Promise<LedgerEntryResponse> {
  const res = await fetch(`${API_BASE_URL}/ledger/repayments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(
      errorBody?.detail ?? `Repayment entry failed with HTTP ${res.status}`
    );
  }
  return res.json();
}

