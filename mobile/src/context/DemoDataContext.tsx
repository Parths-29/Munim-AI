import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  postCredit,
  postRepayment,
  fetchInsightFacts,
  TimelineEvent,
  FactsResponse,
} from '@/api/ledgerClient';
import { ShopPersona } from '@/components/common/PaytmHeader';

export interface DemoCustomer {
  id: string;
  name: string;
  phone: string;
  aliases: string[];
  amountDuePaise: number;
  lastActivity: string;
}

export interface DemoProduct {
  id: string;
  name: string;
  aliases: string[];
  unit: string;
  onHand: number;
  reorderThreshold: number;
  sellingPricePaise: number;
  lastStockoutObservation?: string;
  lastCountUpdate: string;
}

export interface DemoPayment {
  id: string;
  amountPaise: number;
  payerRef: string;
  timestamp: string;
  status: 'SUCCESS' | 'PENDING' | 'FAILED';
  reviewStatus: 'NEEDS_REVIEW' | 'ALLOCATED' | 'IGNORED';
  allocatedToCustomerId?: string;
  allocatedToCustomerName?: string;
}

export interface DemoSupplier {
  id: string;
  name: string;
  contact: string;
  payablePaise: number;
  lastInvoiceDate: string;
}

export interface DemoInvoiceDraft {
  id: string;
  supplierName: string;
  invoiceNumber: string;
  date: string;
  items: {
    productName: string;
    quantity: number;
    unit: string;
    unitCostPaise: number;
    totalPaise: number;
  }[];
  totalPaise: number;
  status: 'DRAFT' | 'CONFIRMED' | 'REJECTED';
  issues: string[];
}

export interface DemoReminder {
  id: string;
  customerId: string;
  customerName: string;
  overdueAmountPaise: number;
  daysOverdue: number;
  maskedPhone: string;
  consentStatus: 'OPTED_IN' | 'OPTED_OUT' | 'PENDING';
  eligibilityStatus: 'ELIGIBLE' | 'BLOCKED_QUIET_HOURS' | 'BLOCKED_NO_CONSENT';
  status: 'AWAITING_APPROVAL' | 'MOCK_SENT' | 'MOCK_DELIVERED';
  messageText: string;
}

interface DemoContextType {
  persona: ShopPersona;
  setPersona: (persona: ShopPersona) => void;

  // Customers & Khata
  customers: DemoCustomer[];
  selectedCustomer: DemoCustomer | null;
  setSelectedCustomer: (c: DemoCustomer | null) => void;
  addCustomer: (name: string, phone: string) => DemoCustomer;
  addCredit: (customerId: string, amountPaise: number, note?: string) => Promise<{ newDuePaise: number }>;
  recordJama: (customerId: string, amountPaise: number, note?: string) => Promise<{ newDuePaise: number }>;

  // Stock
  products: DemoProduct[];
  selectedProduct: DemoProduct | null;
  setSelectedProduct: (p: DemoProduct | null) => void;
  reportStockout: (productId: string) => Promise<void>;
  recordPhysicalCount: (productId: string, quantity: number) => Promise<void>;

  // Payments & Review
  payments: DemoPayment[];
  pendingReviewCount: number;
  allocatePayment: (paymentId: string, customerId: string) => Promise<{ allocatedCustomerName: string; newDuePaise: number }>;
  addSyntheticPayment: (amountPaise: number) => void;

  // Suppliers & Invoices
  suppliers: DemoSupplier[];
  recordSupplierPayment: (supplierId: string, amountPaise: number) => void;
  invoiceDrafts: DemoInvoiceDraft[];
  confirmInvoiceDraft: (draftId: string) => void;

  // Reminders
  reminders: DemoReminder[];
  approveReminder: (reminderId: string) => void;
  mockSendReminder: (reminderId: string) => void;

  // Insights & Growth Action
  facts: FactsResponse | null;
  loadingFacts: boolean;
  approvedGrowthAction: {
    text: string;
    approvedAt: string;
    status: 'ACTIVE_OBSERVATION';
  } | null;
  approveGrowthAction: (text: string) => Promise<void>;

  // Activity Stream
  activityEvents: TimelineEvent[];

  // Reset & Helpers
  resetToDefaultFixture: () => void;
  refreshBackendData: () => Promise<void>;
}

// Initial Fixture according to Section 15
const INITIAL_CUSTOMERS: DemoCustomer[] = [
  {
    id: 'cust_raju_01',
    name: 'Raju bhai',
    phone: '+91 98765 43210',
    aliases: ['raju', 'raju bhai'],
    amountDuePaise: 50000, // ₹500.00
    lastActivity: 'Yesterday',
  },
  {
    id: 'cust_sunita_02',
    name: 'Sunita Devi',
    phone: '+91 98123 45678',
    aliases: ['sunita', 'sunita ji'],
    amountDuePaise: 12000, // ₹120.00
    lastActivity: '3 days ago',
  },
  {
    id: 'cust_amit_03',
    name: 'Amit Kumar',
    phone: '+91 97654 32109',
    aliases: ['amit'],
    amountDuePaise: 0,
    lastActivity: '1 week ago',
  },
];

const INITIAL_PRODUCTS: DemoProduct[] = [
  {
    id: 'prod_maggi_01',
    name: 'Maggi 2-Min Noodles (70g)',
    aliases: ['maggi', 'maggi noodles'],
    unit: 'pack',
    onHand: 12,
    reorderThreshold: 15,
    sellingPricePaise: 1400, // ₹14
    lastCountUpdate: 'Today 09:00 AM',
  },
  {
    id: 'prod_parleg_02',
    name: 'Parle-G Gold Biscuits (100g)',
    aliases: ['parleg', 'parle g'],
    unit: 'pack',
    onHand: 24,
    reorderThreshold: 10,
    sellingPricePaise: 1000, // ₹10
    lastCountUpdate: 'Yesterday',
  },
  {
    id: 'prod_salt_03',
    name: 'Tata Salt (1kg)',
    aliases: ['salt', 'tata salt'],
    unit: 'pack',
    onHand: 18,
    reorderThreshold: 5,
    sellingPricePaise: 2800, // ₹28
    lastCountUpdate: '2 days ago',
  },
];

const INITIAL_PAYMENTS: DemoPayment[] = [
  {
    id: 'pay_sim_01',
    amountPaise: 30000, // ₹300.00
    payerRef: 'Payer_UPI_9876',
    timestamp: 'Today, 10:15 AM',
    status: 'SUCCESS',
    reviewStatus: 'NEEDS_REVIEW',
  },
  {
    id: 'pay_sim_02',
    amountPaise: 15000, // ₹150.00
    payerRef: 'Payer_UPI_1102',
    timestamp: 'Yesterday, 04:30 PM',
    status: 'SUCCESS',
    reviewStatus: 'ALLOCATED',
    allocatedToCustomerId: 'cust_sunita_02',
    allocatedToCustomerName: 'Sunita Devi',
  },
];

const INITIAL_SUPPLIERS: DemoSupplier[] = [
  {
    id: 'supp_01',
    name: 'Krishna FMCG Distributors',
    contact: '+91 99887 76655',
    payablePaise: 1450000, // ₹14,500.00
    lastInvoiceDate: '28 Oct 2026',
  },
  {
    id: 'supp_02',
    name: 'Metro Cash & Carry',
    contact: '+91 98223 34455',
    payablePaise: 820000, // ₹8,200.00
    lastInvoiceDate: '25 Oct 2026',
  },
];

const INITIAL_INVOICES: DemoInvoiceDraft[] = [
  {
    id: 'inv_draft_01',
    supplierName: 'Krishna FMCG Distributors',
    invoiceNumber: 'INV-2026-904',
    date: '31 Oct 2026',
    items: [
      { productName: 'Maggi 2-Min Noodles (70g)', quantity: 24, unit: 'pack', unitCostPaise: 1200, totalPaise: 28800 },
      { productName: 'Parle-G Gold Biscuits (100g)', quantity: 48, unit: 'pack', unitCostPaise: 850, totalPaise: 40800 },
    ],
    totalPaise: 69600,
    status: 'DRAFT',
    issues: ['Pack size conversion applied: 1 Carton = 24 packs'],
  },
];

const INITIAL_REMINDERS: DemoReminder[] = [
  {
    id: 'rem_01',
    customerId: 'cust_raju_01',
    customerName: 'Raju bhai',
    overdueAmountPaise: 50000,
    daysOverdue: 18,
    maskedPhone: '+91 98765 XXXXX',
    consentStatus: 'OPTED_IN',
    eligibilityStatus: 'ELIGIBLE',
    status: 'AWAITING_APPROVAL',
    messageText: 'Namaste Raju bhai, aapka Sharma Kirana Store par ₹500 ka udhaar 18 dino se baki hai. Kripya UPI ya cash se payment karein.',
  },
];

const DemoDataContext = createContext<DemoContextType | null>(null);

export const DemoDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [persona, setPersona] = useState<ShopPersona>('kirana');
  const [customers, setCustomers] = useState<DemoCustomer[]>(INITIAL_CUSTOMERS);
  const [selectedCustomer, setSelectedCustomer] = useState<DemoCustomer | null>(null);

  const [products, setProducts] = useState<DemoProduct[]>(INITIAL_PRODUCTS);
  const [selectedProduct, setSelectedProduct] = useState<DemoProduct | null>(null);

  const [payments, setPayments] = useState<DemoPayment[]>(INITIAL_PAYMENTS);
  const [suppliers, setSuppliers] = useState<DemoSupplier[]>(INITIAL_SUPPLIERS);
  const [invoiceDrafts, setInvoiceDrafts] = useState<DemoInvoiceDraft[]>(INITIAL_INVOICES);
  const [reminders, setReminders] = useState<DemoReminder[]>(INITIAL_REMINDERS);

  const [facts, setFacts] = useState<FactsResponse | null>(null);
  const [loadingFacts, setLoadingFacts] = useState(false);
  const [approvedGrowthAction, setApprovedGrowthAction] = useState<{
    text: string;
    approvedAt: string;
    status: 'ACTIVE_OBSERVATION';
  } | null>(null);

  const [activityEvents, setActivityEvents] = useState<TimelineEvent[]>([
    {
      event_id: 'evt_init_01',
      event_type: 'OPENING_BALANCE',
      entity_type: 'CUSTOMER',
      entity_id: 'cust_raju_01',
      source_event_id: 'src_init_01',
      source_channel: 'MIGRATION',
      source_utterance: null,
      summary: 'Opening due for Raju bhai recorded as ₹500.00',
      created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
      status: 'CONFIRMED',
    },
    {
      event_id: 'evt_init_02',
      event_type: 'STOCK_COUNT',
      entity_type: 'PRODUCT',
      entity_id: 'prod_maggi_01',
      source_event_id: 'src_init_02',
      source_channel: 'PHYSICAL_AUDIT',
      source_utterance: null,
      summary: 'Physical stock count: Maggi at 12 packs',
      created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      status: 'CONFIRMED',
    },
  ]);

  // Load backend facts when persona changes
  const loadFacts = useCallback(async () => {
    setLoadingFacts(true);
    try {
      const data = await fetchInsightFacts(persona);
      setFacts(data);
    } catch {
      // Deterministic fallback handled in UI
    } finally {
      setLoadingFacts(false);
    }
  }, [persona]);

  useEffect(() => {
    loadFacts();
  }, [loadFacts]);

  const pendingReviewCount = payments.filter((p) => p.reviewStatus === 'NEEDS_REVIEW').length;

  // Add Customer
  const addCustomer = useCallback((name: string, phone: string): DemoCustomer => {
    const id = `cust_${Date.now()}`;
    const newCust: DemoCustomer = {
      id,
      name,
      phone,
      aliases: [name.toLowerCase()],
      amountDuePaise: 0,
      lastActivity: 'Just now',
    };
    setCustomers((prev) => [newCust, ...prev]);
    return newCust;
  }, []);

  // 1. Add Udhaar (Credit) -> increases due
  const addCredit = useCallback(
    async (customerId: string, amountPaise: number, note?: string): Promise<{ newDuePaise: number }> => {
      let finalDue = 0;
      setCustomers((prev) =>
        prev.map((c) => {
          if (c.id === customerId) {
            finalDue = c.amountDuePaise + amountPaise;
            return {
              ...c,
              amountDuePaise: finalDue,
              lastActivity: 'Just now',
            };
          }
          return c;
        })
      );

      const cust = customers.find((c) => c.id === customerId);
      const custName = cust?.name || 'Customer';

      // Record in activity
      setActivityEvents((prev) => [
        {
          event_id: `evt_credit_${Date.now()}`,
          event_type: 'CREDIT_ADDED',
          entity_type: 'CUSTOMER',
          entity_id: customerId,
          source_event_id: `src_cred_${Date.now()}`,
          source_channel: 'MERCHANT_COPILOT',
          source_utterance: note || null,
          summary: `Udhaar of ₹${(amountPaise / 100).toFixed(2)} added for ${custName}${note ? ` (${note})` : ''}`,
          created_at: new Date().toISOString(),
          status: 'CONFIRMED',
        },
        ...prev,
      ]);

      // Attempt backend post if possible
      try {
        await postCredit({
          customer_id: customerId,
          amount_paise: amountPaise,
          source_event_id: `evt_cred_${Date.now()}`,
          idempotency_key: `cmd_cred_${Date.now()}`,
          confirmed: true,
        });
      } catch {
        // Safe offline / mock fallback
      }

      return { newDuePaise: finalDue };
    },
    [customers]
  );

  // 2. Record Jama (Repayment) -> decreases due, rejects overpayment
  const recordJama = useCallback(
    async (customerId: string, amountPaise: number, note?: string): Promise<{ newDuePaise: number }> => {
      const cust = customers.find((c) => c.id === customerId);
      if (!cust) throw new Error('Customer not found');

      if (amountPaise > cust.amountDuePaise) {
        throw new Error(`Repayment ₹${(amountPaise / 100).toFixed(2)} exceeds total outstanding balance ₹${(cust.amountDuePaise / 100).toFixed(2)}.`);
      }

      const finalDue = cust.amountDuePaise - amountPaise;
      setCustomers((prev) =>
        prev.map((c) =>
          c.id === customerId
            ? { ...c, amountDuePaise: finalDue, lastActivity: 'Just now' }
            : c
        )
      );

      setActivityEvents((prev) => [
        {
          event_id: `evt_jama_${Date.now()}`,
          event_type: 'JAMA_RECORDED',
          entity_type: 'CUSTOMER',
          entity_id: customerId,
          source_event_id: `src_jama_${Date.now()}`,
          source_channel: 'MERCHANT_COPILOT',
          source_utterance: note || null,
          summary: `Repayment (Jama) of ₹${(amountPaise / 100).toFixed(2)} received from ${cust.name}`,
          created_at: new Date().toISOString(),
          status: 'CONFIRMED',
        },
        ...prev,
      ]);

      try {
        await postRepayment({
          customer_id: customerId,
          amount_paise: amountPaise,
          source_event_id: `evt_jama_${Date.now()}`,
          idempotency_key: `cmd_jama_${Date.now()}`,
          confirmed: true,
        });
      } catch {
        // Fallback
      }

      return { newDuePaise: finalDue };
    },
    [customers]
  );

  // 3. Allocate Payment (Links synthetic payment to customer, reducing due)
  const allocatePayment = useCallback(
    async (paymentId: string, customerId: string) => {
      const payment = payments.find((p) => p.id === paymentId);
      const cust = customers.find((c) => c.id === customerId);
      if (!payment || !cust) throw new Error('Invalid payment or customer');

      if (payment.amountPaise > cust.amountDuePaise) {
        throw new Error(
          `Payment amount ₹${(payment.amountPaise / 100).toFixed(2)} cannot exceed current due ₹${(cust.amountDuePaise / 100).toFixed(2)}.`
        );
      }

      const newDue = cust.amountDuePaise - payment.amountPaise;

      setCustomers((prev) =>
        prev.map((c) =>
          c.id === customerId ? { ...c, amountDuePaise: newDue, lastActivity: 'Payment matched just now' } : c
        )
      );

      setPayments((prev) =>
        prev.map((p) =>
          p.id === paymentId
            ? {
                ...p,
                reviewStatus: 'ALLOCATED',
                allocatedToCustomerId: customerId,
                allocatedToCustomerName: cust.name,
              }
            : p
        )
      );

      setActivityEvents((prev) => [
        {
          event_id: `evt_alloc_${Date.now()}`,
          event_type: 'PAYMENT_ALLOCATED',
          entity_type: 'CUSTOMER',
          entity_id: customerId,
          source_event_id: paymentId,
          source_channel: 'MANUAL_ALLOCATION',
          source_utterance: null,
          summary: `Payment ₹${(payment.amountPaise / 100).toFixed(2)} allocated to ${cust.name}. Remaining due: ₹${(newDue / 100).toFixed(2)}`,
          created_at: new Date().toISOString(),
          status: 'CONFIRMED',
        },
        ...prev,
      ]);

      return { allocatedCustomerName: cust.name, newDuePaise: newDue };
    },
    [payments, customers]
  );

  // 4. Add Synthetic Payment to review queue
  const addSyntheticPayment = useCallback((amountPaise: number) => {
    const newPayment: DemoPayment = {
      id: `pay_sim_${Date.now()}`,
      amountPaise,
      payerRef: `Payer_UPI_${Math.floor(1000 + Math.random() * 9000)}`,
      timestamp: 'Just now',
      status: 'SUCCESS',
      reviewStatus: 'NEEDS_REVIEW',
    };
    setPayments((prev) => [newPayment, ...prev]);

    setActivityEvents((prev) => [
      {
        event_id: `evt_pay_intake_${Date.now()}`,
        event_type: 'PAYMENT_RECEIVED',
        entity_type: 'PAYMENT',
        entity_id: newPayment.id,
        source_event_id: `src_pay_${Date.now()}`,
        source_channel: 'PAYMENT_INTAKE',
        source_utterance: null,
        summary: `Mock UPI payment of ₹${(amountPaise / 100).toFixed(2)} received (Queued for Review)`,
        created_at: new Date().toISOString(),
        status: 'NEEDS_REVIEW',
      },
      ...prev,
    ]);
  }, []);

  // 5. Stockout Observation (Leaves quantity UNCHANGED per specs)
  const reportStockout = useCallback(async (productId: string) => {
    const prod = products.find((p) => p.id === productId);
    if (!prod) return;

    setProducts((prev) =>
      prev.map((p) =>
        p.id === productId
          ? { ...p, lastStockoutObservation: 'Stockout reported just now' }
          : p
      )
    );

    setActivityEvents((prev) => [
      {
        event_id: `evt_stockout_${Date.now()}`,
        event_type: 'STOCKOUT_OBSERVATION',
        entity_type: 'PRODUCT',
        entity_id: productId,
        source_event_id: `src_obs_${Date.now()}`,
        source_channel: 'MERCHANT_OBSERVATION',
        source_utterance: null,
        summary: `Stockout observation recorded for ${prod.name}. On-hand remains unchanged at ${prod.onHand} ${prod.unit}s.`,
        created_at: new Date().toISOString(),
        status: 'CONFIRMED',
      },
      ...prev,
    ]);
  }, [products]);

  // 6. Physical Count (Explicitly mutates on-hand quantity)
  const recordPhysicalCount = useCallback(async (productId: string, quantity: number) => {
    const prod = products.find((p) => p.id === productId);
    if (!prod) return;

    setProducts((prev) =>
      prev.map((p) =>
        p.id === productId
          ? {
              ...p,
              onHand: quantity,
              lastStockoutObservation: undefined,
              lastCountUpdate: 'Count updated just now',
            }
          : p
      )
    );

    setActivityEvents((prev) => [
      {
        event_id: `evt_count_${Date.now()}`,
        event_type: 'PHYSICAL_COUNT',
        entity_type: 'PRODUCT',
        entity_id: productId,
        source_event_id: `src_count_${Date.now()}`,
        source_channel: 'MERCHANT_PHYSICAL_COUNT',
        source_utterance: null,
        summary: `Physical count confirmed: ${prod.name} updated to ${quantity} ${prod.unit}s (was ${prod.onHand})`,
        created_at: new Date().toISOString(),
        status: 'CONFIRMED',
      },
      ...prev,
    ]);
  }, [products]);

  // 7. Approve Growth Action
  const approveGrowthAction = useCallback(async (text: string) => {
    setApprovedGrowthAction({
      text,
      approvedAt: new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
      status: 'ACTIVE_OBSERVATION',
    });

    setActivityEvents((prev) => [
      {
        event_id: `evt_action_${Date.now()}`,
        event_type: 'GROWTH_ACTION_APPROVED',
        entity_type: 'ACTION',
        entity_id: `act_${Date.now()}`,
        source_event_id: `src_act_${Date.now()}`,
        source_channel: 'MERCHANT_APPROVAL',
        source_utterance: text,
        summary: `Merchant approved growth action: "${text}" (7-Day Tracking Scheduled)`,
        created_at: new Date().toISOString(),
        status: 'CONFIRMED',
      },
      ...prev,
    ]);
  }, []);

  // 8. Record Supplier Payment
  const recordSupplierPayment = useCallback((supplierId: string, amountPaise: number) => {
    const supp = suppliers.find((s) => s.id === supplierId);
    if (!supp) return;

    const newPayable = Math.max(0, supp.payablePaise - amountPaise);
    setSuppliers((prev) =>
      prev.map((s) => (s.id === supplierId ? { ...s, payablePaise: newPayable } : s))
    );

    setActivityEvents((prev) => [
      {
        event_id: `evt_supp_pay_${Date.now()}`,
        event_type: 'SUPPLIER_PAYMENT',
        entity_type: 'SUPPLIER',
        entity_id: supplierId,
        source_event_id: `src_supp_${Date.now()}`,
        source_channel: 'SUPPLIER_KHATA',
        source_utterance: null,
        summary: `Accounting record: ₹${(amountPaise / 100).toFixed(2)} payment recorded for ${supp.name}`,
        created_at: new Date().toISOString(),
        status: 'CONFIRMED',
      },
      ...prev,
    ]);
  }, [suppliers]);

  // 9. Confirm Inward Invoice Draft
  const confirmInvoiceDraft = useCallback((draftId: string) => {
    const draft = invoiceDrafts.find((d) => d.id === draftId);
    if (!draft) return;

    // Update status
    setInvoiceDrafts((prev) =>
      prev.map((d) => (d.id === draftId ? { ...d, status: 'CONFIRMED' } : d))
    );

    // Increase stock for items
    draft.items.forEach((item) => {
      setProducts((prev) =>
        prev.map((p) =>
          p.name.includes('Maggi') && item.productName.includes('Maggi')
            ? { ...p, onHand: p.onHand + item.quantity }
            : p.name.includes('Parle') && item.productName.includes('Parle')
            ? { ...p, onHand: p.onHand + item.quantity }
            : p
        )
      );
    });

    setActivityEvents((prev) => [
      {
        event_id: `evt_inv_confirm_${Date.now()}`,
        event_type: 'STOCK_INWARD_CONFIRMED',
        entity_type: 'INVOICE',
        entity_id: draftId,
        source_event_id: draft.invoiceNumber,
        source_channel: 'INVOICE_SCAN',
        source_utterance: null,
        summary: `Supplier bill #${draft.invoiceNumber} posted: Stock inward confirmed for ${draft.items.length} items.`,
        created_at: new Date().toISOString(),
        status: 'CONFIRMED',
      },
      ...prev,
    ]);
  }, [invoiceDrafts]);

  // 10. Reminders
  const approveReminder = useCallback((reminderId: string) => {
    setReminders((prev) =>
      prev.map((r) => (r.id === reminderId ? { ...r, status: 'MOCK_SENT' } : r))
    );

    setActivityEvents((prev) => [
      {
        event_id: `evt_rem_approve_${Date.now()}`,
        event_type: 'REMINDER_APPROVED',
        entity_type: 'REMINDER',
        entity_id: reminderId,
        source_event_id: `src_rem_${Date.now()}`,
        source_channel: 'MERCHANT_APPROVAL',
        source_utterance: null,
        summary: `Reminder approved for Raju bhai (Simulated sending queued)`,
        created_at: new Date().toISOString(),
        status: 'CONFIRMED',
      },
      ...prev,
    ]);
  }, []);

  const mockSendReminder = useCallback((reminderId: string) => {
    setReminders((prev) =>
      prev.map((r) => (r.id === reminderId ? { ...r, status: 'MOCK_DELIVERED' } : r))
    );
  }, []);

  // Reset to default fixture
  const resetToDefaultFixture = useCallback(() => {
    setCustomers(INITIAL_CUSTOMERS);
    setProducts(INITIAL_PRODUCTS);
    setPayments(INITIAL_PAYMENTS);
    setSuppliers(INITIAL_SUPPLIERS);
    setInvoiceDrafts(INITIAL_INVOICES);
    setReminders(INITIAL_REMINDERS);
    setApprovedGrowthAction(null);
  }, []);

  const refreshBackendData = useCallback(async () => {
    await loadFacts();
  }, [loadFacts]);

  return (
    <DemoDataContext.Provider
      value={{
        persona,
        setPersona,
        customers,
        selectedCustomer,
        setSelectedCustomer,
        addCustomer,
        addCredit,
        recordJama,
        products,
        selectedProduct,
        setSelectedProduct,
        reportStockout,
        recordPhysicalCount,
        payments,
        pendingReviewCount,
        allocatePayment,
        addSyntheticPayment,
        suppliers,
        recordSupplierPayment,
        invoiceDrafts,
        confirmInvoiceDraft,
        reminders,
        approveReminder,
        mockSendReminder,
        facts,
        loadingFacts,
        approvedGrowthAction,
        approveGrowthAction,
        activityEvents,
        resetToDefaultFixture,
        refreshBackendData,
      }}
    >
      {children}
    </DemoDataContext.Provider>
  );
};

export const useDemoData = () => {
  const context = useContext(DemoDataContext);
  if (!context) {
    throw new Error('useDemoData must be used within a DemoDataProvider');
  }
  return context;
};
