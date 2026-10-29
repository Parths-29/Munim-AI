/**
 * Comprehensive Typed client for KiranaOS Backend API v0.5
 * Ref: docs/contracts/backend-api-v0.md (origin/codex/payment-review)
 *
 * Implements:
 * - GET  /health
 * - POST /customers
 * - GET  /customers/resolve?query=...
 * - GET  /ledger/customers/{customer_id}/balance
 * - POST /ledger/credits
 * - POST /ledger/repayments
 * - POST /products
 * - GET  /products/resolve?query=...
 * - GET  /inventory/products/{product_id}/stock
 * - POST /inventory/stockout-observations
 * - POST /inventory/counts
 * - GET  /events?limit=50
 * - GET  /insights/facts?persona=...
 * - GET  /payments/review
 * - POST /payments/{event_id}/allocate
 *
 * NOTE: All data is synthetic mock demo data.
 * No live Paytm integration exists or is claimed.
 */

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: string;
  phase: string;
  data_mode: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed with HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------
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

export async function resolveCustomer(query: string): Promise<CustomerResolveResponse> {
  const res = await fetch(`${API_BASE_URL}/customers/resolve?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Customer resolve failed with HTTP ${res.status}`);
  return res.json();
}

export async function createCustomer(req: CreateCustomerRequest): Promise<Customer> {
  const res = await fetch(`${API_BASE_URL}/customers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Create customer failed with HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Ledger
// ---------------------------------------------------------------------------
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

export async function fetchCustomerBalance(customerId: string): Promise<CustomerBalanceResponse> {
  const res = await fetch(`${API_BASE_URL}/ledger/customers/${encodeURIComponent(customerId)}/balance`);
  if (!res.ok) throw new Error(`Fetch balance failed with HTTP ${res.status}`);
  return res.json();
}

export async function postCredit(req: LedgerEntryRequest): Promise<LedgerEntryResponse> {
  const res = await fetch(`${API_BASE_URL}/ledger/credits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Credit entry failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function postRepayment(req: LedgerEntryRequest): Promise<LedgerEntryResponse> {
  const res = await fetch(`${API_BASE_URL}/ledger/repayments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Repayment entry failed with HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Products & Inventory
// ---------------------------------------------------------------------------
export interface Product {
  product_id: string;
  name: string;
  aliases: string[];
  unit: string;
}

export interface CreateProductRequest {
  name: string;
  aliases: string[];
  unit: string;
  confirmed: boolean;
  idempotency_key: string;
  source_utterance?: string;
  source_channel?: string;
}

export interface ProductResolveResponse {
  status: 'RESOLVED' | 'AMBIGUOUS' | 'NOT_FOUND';
  query: string;
  product?: Product;
  matches?: Product[];
}

export interface ProductStockResponse {
  product_id: string;
  product_name?: string;
  on_hand_quantity: number;
  unit: string;
  movement_count: number;
}

export interface StockoutObservationRequest {
  product_id: string;
  source_event_id: string;
  idempotency_key: string;
  confirmed: boolean;
  source_utterance?: string;
  source_channel?: string;
}

export interface StockoutObservationResponse {
  observation_id: string;
  product_id: string;
  status: 'OBSERVED';
  note: string;
}

export interface PhysicalCountRequest {
  product_id: string;
  counted_quantity: number;
  source_event_id: string;
  idempotency_key: string;
  confirmed: boolean;
  source_utterance?: string;
  source_channel?: string;
}

export interface PhysicalCountResponse {
  movement_id: string;
  product_id: string;
  previous_quantity: number;
  counted_quantity: number;
  quantity_delta: number;
  type: 'PHYSICAL_COUNT';
}

export async function createProduct(req: CreateProductRequest): Promise<Product> {
  const res = await fetch(`${API_BASE_URL}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Create product failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function resolveProduct(query: string): Promise<ProductResolveResponse> {
  const res = await fetch(`${API_BASE_URL}/products/resolve?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Product resolve failed with HTTP ${res.status}`);
  return res.json();
}

export async function fetchProductStock(productId: string): Promise<ProductStockResponse> {
  const res = await fetch(`${API_BASE_URL}/inventory/products/${encodeURIComponent(productId)}/stock`);
  if (!res.ok) throw new Error(`Fetch product stock failed with HTTP ${res.status}`);
  return res.json();
}

export async function recordStockoutObservation(req: StockoutObservationRequest): Promise<StockoutObservationResponse> {
  const res = await fetch(`${API_BASE_URL}/inventory/stockout-observations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Stockout observation failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function recordPhysicalCount(req: PhysicalCountRequest): Promise<PhysicalCountResponse> {
  const res = await fetch(`${API_BASE_URL}/inventory/counts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Physical count update failed with HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Activity Timeline Events
// ---------------------------------------------------------------------------
export interface TimelineEvent {
  event_id: string;
  event_type: string;
  related_entity_id?: string | null;
  source_channel?: string | null;
  source_utterance?: string | null;
  status: string;
  summary: string;
  created_at: string;
}

export async function fetchEvents(limit: number = 50): Promise<TimelineEvent[]> {
  const res = await fetch(`${API_BASE_URL}/events?limit=${limit}`);
  if (!res.ok) throw new Error(`Fetch events failed with HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Business Insights Facts
// ---------------------------------------------------------------------------
export type Persona = 'kirana' | 'tea_stall' | 'medical_store';

export interface InsightFact {
  id: string;
  label: string;
  status: 'available' | 'unavailable' | 'needs_confirmation' | 'low_sample';
  value: number | string | boolean | null;
  unit: string | null;
  source: string;
  count: number | null;
  comparison_value?: number | string | boolean | null;
  comparison_period?: string | null;
  definition?: string | null;
  reason_unavailable?: string | null;
}

export interface FactsResponse {
  schema_version: string;
  shop_id: string;
  data_mode: 'synthetic';
  period: {
    start: string;
    end: string;
    timezone: string;
  };
  facts: InsightFact[];
  evidence_ids: string[];
  caveats: string[];
  allowed_actions: string[];
}

export async function fetchInsightFacts(persona: Persona = 'kirana'): Promise<FactsResponse> {
  const res = await fetch(`${API_BASE_URL}/insights/facts?persona=${encodeURIComponent(persona)}`);
  if (!res.ok) throw new Error(`Fetch insights facts failed with HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Payment Review & Manual Allocation
// ---------------------------------------------------------------------------
export interface PaymentReviewItem {
  event_id: string;
  amount_paise: number;
  status: string;
  payer_token?: string | null;
  occurred_at: string;
  source: string;
  unresolved_reason?: string | null;
}

export interface ManualAllocateRequest {
  customer_id: string;
  confirmed: boolean;
  idempotency_key: string;
}

export interface ManualAllocateResponse {
  allocation_id: string;
  event_id: string;
  customer_id: string;
  amount_paise: number;
  decision_status: 'ALLOCATED';
  ledger_entry_id: string;
}

export async function fetchPaymentReviewQueue(): Promise<PaymentReviewItem[]> {
  const res = await fetch(`${API_BASE_URL}/payments/review`);
  if (!res.ok) throw new Error(`Fetch payment review queue failed with HTTP ${res.status}`);
  return res.json();
}

export async function allocatePaymentManually(
  eventId: string,
  req: ManualAllocateRequest
): Promise<ManualAllocateResponse> {
  const res = await fetch(`${API_BASE_URL}/payments/${encodeURIComponent(eventId)}/allocate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Payment allocation failed with HTTP ${res.status}`);
  }
  return res.json();
}
