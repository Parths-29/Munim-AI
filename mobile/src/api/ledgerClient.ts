import { Platform } from 'react-native';

/**
 * Comprehensive Typed client for KiranaOS Backend API v0.5
 * Ref: docs/contracts/backend-api-v0.md
 *
 * All financial values are integer paise.
 * Demo shop is fixed to `shop_synth_01`.
 * All data is strictly synthetic demo data.
 * No connection to live Paytm systems is claimed.
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
  source_utterance?: string;
  source_channel?: 'text' | 'voice' | 'provider_mock' | 'system';
}

export type CustomerResolveStatus = 'RESOLVED' | 'AMBIGUOUS' | 'NOT_FOUND';

export interface CustomerResolveResponse {
  status: CustomerResolveStatus;
  query: string;
  matches: Customer[];
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
  entry_count: number;
}

export interface LedgerEntryRequest {
  customer_id: string;
  amount_paise: number;
  source_event_id: string;
  idempotency_key: string;
  confirmed: boolean;
  source_utterance?: string;
  source_channel?: 'text' | 'voice' | 'provider_mock' | 'system';
}

export interface LedgerEntryResponse {
  entry_id: string;
  customer_id: string;
  entry_type: 'CREDIT' | 'REPAYMENT';
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
  source_channel?: 'text' | 'voice' | 'provider_mock' | 'system';
}

export interface ProductResolveResponse {
  status: 'RESOLVED' | 'AMBIGUOUS' | 'NOT_FOUND';
  query: string;
  matches: Product[];
}

export interface ProductStockResponse {
  product_id: string;
  product_name: string;
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
  source_channel?: 'text' | 'voice' | 'provider_mock' | 'system';
}

export interface StockoutObservationResponse {
  observation_id: string;
  product_id: string;
  status: 'OBSERVED';
  source_event_id: string;
  created_at: string;
  idempotent_replay: boolean;
}

export interface PhysicalCountRequest {
  product_id: string;
  counted_quantity: number;
  source_event_id: string;
  idempotency_key: string;
  confirmed: boolean;
  source_utterance?: string;
  source_channel?: 'text' | 'voice' | 'provider_mock' | 'system';
}

export interface PhysicalCountResponse {
  movement_id: string;
  product_id: string;
  counted_quantity: number;
  quantity_delta: number;
  unit: string;
  reason: 'PHYSICAL_COUNT';
  status: 'POSTED';
  source_event_id: string;
  created_at: string;
  idempotent_replay: boolean;
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
  entity_type: string;
  entity_id: string;
  source_event_id: string;
  source_channel: string;
  source_utterance: string | null;
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
  data_mode: 'synthetic' | 'merchant_entered' | 'provider_mock';
  period: {
    start: string;
    end: string;
    timezone: string;
  };
  facts: InsightFact[];
  evidence_ids: string[];
  caveats: string[];
  allowed_actions: ('counter_notice' | 'qr_offer_mock' | 'review_payment' | 'confirm_stock_count')[];
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
  resolution_status: string;
  reason: string | null;
  occurred_at: string;
  created_at: string;
}

export interface ManualAllocateRequest {
  customer_id: string;
  confirmed: boolean;
  idempotency_key: string;
}

export interface MockPaymentIntakeRequest {
  event_id: string;
  amount_paise: number;
  status: 'SUCCESS' | 'PENDING' | 'FAILED' | 'REVERSED';
  occurred_at: string;
  idempotency_key: string;
  payer_token?: string | null;
  source: 'provider_mock';
}

export interface MockPaymentIntakeResponse {
  event_id: string;
  amount_paise: number;
  status: string;
  resolution_status: string;
  reason: string | null;
  allocation_entry_id: string | null;
  created_at: string;
  idempotent_replay: boolean;
}

export interface ManualAllocateResponse {
  event_id: string;
  customer_id: string;
  amount_paise: number;
  allocation_entry_id: string;
  status: 'ALLOCATED';
  idempotent_replay?: boolean;
}

export async function fetchPaymentReviewQueue(): Promise<PaymentReviewItem[]> {
  const res = await fetch(`${API_BASE_URL}/payments/review`);
  if (!res.ok) throw new Error(`Fetch payment review queue failed with HTTP ${res.status}`);
  return res.json();
}

export async function intakeMockPayment(req: MockPaymentIntakeRequest): Promise<MockPaymentIntakeResponse> {
  const res = await fetch(`${API_BASE_URL}/payments/intake`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Mock payment intake failed with HTTP ${res.status}`);
  }
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

// ---------------------------------------------------------------------------
// AI Brief Explanation (facts-only, server-side validated)
// ---------------------------------------------------------------------------
export type ActionType = 'counter_notice' | 'qr_offer_mock';

export interface BriefExplanationResponse {
  explanation: string;
  evidence_ids: string[];
  proposed_action: string;
  action_type: ActionType;
  fallback_used: boolean;
  validation_errors: string[];
}

export async function fetchBriefExplanation(
  persona: Persona = 'kirana',
): Promise<BriefExplanationResponse> {
  const res = await fetch(
    `${API_BASE_URL}/insights/explain`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona }),
    },
  );
  if (!res.ok) throw new Error(`Fetch brief explanation failed with HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Merchant-approved mock action and outcome tracking
// ---------------------------------------------------------------------------
export interface MockActionResponse {
  action_id: string;
  action_type: ActionType;
  action_text: string;
  status: 'APPROVED_MOCK';
  mock_only: true;
  created_at: string;
  baseline_start: string;
  baseline_end: string;
  baseline_collections_paise: number;
  baseline_transaction_count: number;
  measurement_start: string;
  measurement_end: string;
  outcome_status: 'scheduled' | 'available' | 'insufficient_data';
  outcome_collections_paise: number | null;
  outcome_transaction_count: number | null;
  collections_change_paise: number | null;
  outcome_note: string;
}

export interface ApproveMockActionRequest {
  persona: Persona;
  action_type: ActionType;
  action_text: string;
  confirmed: true;
  idempotency_key: string;
}

export async function approveMockAction(req: ApproveMockActionRequest): Promise<MockActionResponse> {
  const res = await fetch(`${API_BASE_URL}/actions/mock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Mock action approval failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchLatestMockAction(persona: Persona = 'kirana'): Promise<MockActionResponse | null> {
  const res = await fetch(`${API_BASE_URL}/actions/latest?persona=${encodeURIComponent(persona)}`);
  if (!res.ok) throw new Error(`Fetch latest mock action failed with HTTP ${res.status}`);
  return res.json();
}

export interface SpeechTranscriptionResponse {
  transcript: string;
  language_code: string | null;
  request_id: string | null;
  provider: 'sarvam';
}

export async function transcribeMerchantAudio(uri: string): Promise<SpeechTranscriptionResponse> {
  const form = new FormData();
  if (Platform.OS === 'web') {
    // Expo Audio records WebM in browsers. Browser FormData needs a real Blob;
    // React Native's { uri, name, type } file descriptor only works natively.
    const audioResponse = await fetch(uri);
    if (!audioResponse.ok) throw new Error('Could not read the browser recording. Please record again.');
    const audioBlob = await audioResponse.blob();
    const contentType = audioBlob.type?.split(';', 1)[0] || 'audio/webm';
    const extension = contentType.includes('webm') ? 'webm' : contentType.includes('wav') ? 'wav' : 'm4a';
    form.append('file', audioBlob, `merchant-voice.${extension}`);
  } else {
    form.append('file', {
      uri,
      name: 'merchant-voice.m4a',
      type: 'audio/mp4',
    } as unknown as Blob);
  }
  const res = await fetch(`${API_BASE_URL}/speech/transcribe`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Voice transcription failed with HTTP ${res.status}`);
  }
  return res.json();
}
