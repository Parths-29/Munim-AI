/**
 * HomeScreen — KiranaOS / Munim-AI Mobile Hub
 *
 * Provides tabbed navigation across:
 * 1. Copilot (Voice/text commands, credit/repayment, customer resolve, derived balance,
 *    and end-to-end "Aaj kaisa raha?" insights brief slice)
 * 2. Pay Review (GET /payments/review & merchant-confirmed manual allocation)
 * 3. Inventory (Stock lookup, stockout observation, physical counts)
 * 4. Timeline (Activity stream from GET /events)
 * 5. Insights (Computed facts, evidence IDs, caveats from GET /insights/facts)
 *
 * Integrity:
 * - All data is synthetic. No live Paytm integration.
 * - Balance is derived, not LLM-invented.
 * - Stockout is an observation; counts require physical confirmation.
 * - "Aaj kaisa raha?" loads /insights/facts?persona=kirana with caveats and mocked action.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { InfoBanner, SyntheticDataPill } from '@/components/InfoBanner';
import {
  resolveCustomer,
  createCustomer,
  fetchCustomerBalance,
  postCredit,
  postRepayment,
  fetchInsightFacts,
  FactsResponse,
} from '@/api/ledgerClient';
import PaymentReviewScreen from '@/features/paymentReview/PaymentReviewScreen';
import InventoryScreen from '@/features/inventory/InventoryScreen';
import TimelineScreen from '@/features/timeline/TimelineScreen';
import InsightsScreen from '@/features/insights/InsightsScreen';
import { formatFactComparison, formatFactDefinition, formatFactValue, formatPeriodDate } from '@/utils/formatters';

type Tab = 'copilot' | 'payment_review' | 'inventory' | 'timeline' | 'insights';

interface HistoryEntry {
  id: string;
  text: string;
  timestamp: string;
  isInsightQuery?: boolean;
}

const EXAMPLE_PROMPTS = [
  'Aaj kaisa raha?',
  'Raju bhai ka ₹50 udhaar likh do',
  'Raju bhai ka ₹30 jamma kar lo',
  'Raju bhai ka balance batao',
  'Maggi khatam ho gaya',
];

export default function HomeScreen() {
  const [activeTab, setActiveTab] = useState<Tab>('copilot');

  // Copilot text state
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCustomerId, setActiveCustomerId] = useState<string | null>(null);
  const [customerName] = useState('Raju bhai');
  const [customerBalance, setCustomerBalance] = useState<number | null>(null);

  // "Aaj kaisa raha?" end-to-end slice state
  const [insightsBrief, setInsightsBrief] = useState<FactsResponse | null>(null);
  const [mockOfferApproved, setMockOfferApproved] = useState(false);
  const [mockOfferText, setMockOfferText] = useState("Weekend special: ask us about today's offer");

  // Trigger "Aaj kaisa raha?" insight slice
  const handleLoadInsightsBrief = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchInsightFacts('kirana');
      setInsightsBrief(data);
      setMockOfferApproved(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Could Not Load Business Brief', `${message}\nEnsure backend is running at ${process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'}`);
    } finally {
      setLoading(false);
    }
  }, []);

  // Quick Action: Resolve / Check Balance
  const handleCheckRajuBalance = async () => {
    setLoading(true);
    try {
      let custId = activeCustomerId;
      if (!custId) {
        const res = await resolveCustomer(customerName);
        if (res.status === 'RESOLVED' && res.matches.length === 1) {
          custId = res.matches[0].customer_id;
          setActiveCustomerId(custId);
        } else if (res.status === 'NOT_FOUND') {
          Alert.alert('Customer Not Found', `Add ${customerName} before checking a balance.`);
          return;
        } else {
          Alert.alert('Ambiguous Match', `Multiple customers found for "${customerName}".`);
          return;
        }
      }
      const bal = await fetchCustomerBalance(custId);
      setCustomerBalance(bal.balance_due_paise);
      Alert.alert(
        'Derived Customer Balance',
        `${customerName} (ID: ${custId})\nOutstanding: ₹${(bal.balance_due_paise / 100).toFixed(2)}\nEntries: ${bal.entry_count}`
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Balance Lookup Failed', message);
    } finally {
      setLoading(false);
    }
  };

  // Quick Action: Credit ₹50
  const handleQuickCredit = async () => {
    setLoading(true);
    try {
      let custId = activeCustomerId;
      if (!custId) {
        const res = await resolveCustomer(customerName);
        if (res.status === 'RESOLVED' && res.matches.length === 1) {
          custId = res.matches[0].customer_id;
          setActiveCustomerId(custId);
        } else if (res.status === 'NOT_FOUND') {
          const created = await createCustomer({
            display_name: customerName,
            aliases: ['Raju', 'Raju bhai'],
            confirmed: true,
            idempotency_key: `cmd_seed_raju_${Date.now()}`,
          });
          custId = created.customer_id;
          setActiveCustomerId(custId);
        } else {
          Alert.alert('Ambiguous Match', `Multiple customers found for "${customerName}". Resolve the correct customer before posting credit.`);
          return;
        }
      }
      const creditRes = await postCredit({
        customer_id: custId,
        amount_paise: 5000,
        source_event_id: `evt_cred_${Date.now()}`,
        idempotency_key: `cmd_cred_${Date.now()}`,
        confirmed: true,
      });
      const bal = await fetchCustomerBalance(custId);
      setCustomerBalance(bal.balance_due_paise);
      Alert.alert(
        'Credit Posted Successfully',
        `₹50.00 udhaar posted for ${customerName}.\nNew Derived Balance: ₹${(bal.balance_due_paise / 100).toFixed(2)}\nEntry ID: ${creditRes.entry_id}`
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Credit Failed', message);
    } finally {
      setLoading(false);
    }
  };

  // Quick Action: Repayment ₹30
  const handleQuickRepayment = async () => {
    setLoading(true);
    try {
      let custId = activeCustomerId;
      if (!custId) {
        const res = await resolveCustomer(customerName);
        if (res.status === 'RESOLVED' && res.matches.length === 1) {
          custId = res.matches[0].customer_id;
          setActiveCustomerId(custId);
        } else {
          Alert.alert(res.status === 'AMBIGUOUS' ? 'Ambiguous Customer' : 'Customer Not Found', 'Resolve the correct customer before posting repayment.');
          return;
        }
      }
      const repayRes = await postRepayment({
        customer_id: custId,
        amount_paise: 3000,
        source_event_id: `evt_repay_${Date.now()}`,
        idempotency_key: `cmd_repay_${Date.now()}`,
        confirmed: true,
      });
      const bal = await fetchCustomerBalance(custId);
      setCustomerBalance(bal.balance_due_paise);
      Alert.alert(
        'Repayment Posted Successfully',
        `₹30.00 repayment posted for ${customerName}.\nRemaining Balance: ₹${(bal.balance_due_paise / 100).toFixed(2)}\nEntry ID: ${repayRes.entry_id}`
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Repayment Failed', message);
    } finally {
      setLoading(false);
    }
  };

  const handlePromptPress = (prompt: string) => {
    setInput(prompt);
    if (prompt.toLowerCase().includes('aaj kaisa raha')) {
      handleLoadInsightsBrief();
    }
  };

  const handleSubmitText = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed) return;

    const isInsight = trimmed.toLowerCase().includes('kaisa raha') || trimmed.toLowerCase().includes('summary');
    const entry: HistoryEntry = {
      id: `local-${Date.now()}`,
      text: trimmed,
      timestamp: new Date().toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      isInsightQuery: isInsight,
    };
    setHistory((prev) => [entry, ...prev]);
    setInput('');

    if (isInsight) {
      handleLoadInsightsBrief();
    }
  }, [input, handleLoadInsightsBrief]);

  return (
    <SafeAreaView style={styles.safe}>
      {/* ── App Top Header ────────────────────────────────────────────── */}
      <View style={styles.topBar}>
        <View>
          <Text style={styles.appName}>Munim-AI</Text>
          <Text style={styles.tagline}>KiranaOS Shop Copilot · Synthetic Memory</Text>
        </View>
        <View style={styles.syntheticBadge}>
          <Text style={styles.syntheticBadgeText}>SYNTHETIC DEMO</Text>
        </View>
      </View>

      {/* ── Segmented Navigation Bar ──────────────────────────────────── */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'copilot' && styles.tabItemActive]}
          onPress={() => setActiveTab('copilot')}
        >
          <Ionicons name="chatbox-ellipses-outline" size={16} color={activeTab === 'copilot' ? '#0f3460' : '#6c757d'} />
          <Text style={[styles.tabLabel, activeTab === 'copilot' && styles.tabLabelActive]}>Copilot</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'payment_review' && styles.tabItemActive]}
          onPress={() => setActiveTab('payment_review')}
        >
          <Ionicons name="card-outline" size={16} color={activeTab === 'payment_review' ? '#0f3460' : '#6c757d'} />
          <Text style={[styles.tabLabel, activeTab === 'payment_review' && styles.tabLabelActive]}>Pay Review</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'inventory' && styles.tabItemActive]}
          onPress={() => setActiveTab('inventory')}
        >
          <Ionicons name="cube-outline" size={16} color={activeTab === 'inventory' ? '#0f3460' : '#6c757d'} />
          <Text style={[styles.tabLabel, activeTab === 'inventory' && styles.tabLabelActive]}>Inventory</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'timeline' && styles.tabItemActive]}
          onPress={() => setActiveTab('timeline')}
        >
          <Ionicons name="time-outline" size={16} color={activeTab === 'timeline' ? '#0f3460' : '#6c757d'} />
          <Text style={[styles.tabLabel, activeTab === 'timeline' && styles.tabLabelActive]}>Timeline</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'insights' && styles.tabItemActive]}
          onPress={() => setActiveTab('insights')}
        >
          <Ionicons name="bar-chart-outline" size={16} color={activeTab === 'insights' ? '#0f3460' : '#6c757d'} />
          <Text style={[styles.tabLabel, activeTab === 'insights' && styles.tabLabelActive]}>Insights</Text>
        </TouchableOpacity>
      </View>

      {/* ── Tab Views ─────────────────────────────────────────────────── */}
      {activeTab === 'payment_review' && <PaymentReviewScreen />}
      {activeTab === 'inventory' && <InventoryScreen />}
      {activeTab === 'timeline' && <TimelineScreen />}
      {activeTab === 'insights' && <InsightsScreen />}

      {activeTab === 'copilot' && (
        <View style={styles.copilotContainer}>
          <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
            <SyntheticDataPill />

            <InfoBanner text="Voice STT and live Paytm servers are not connected. Showing deterministic backend memory & insights." />

            {/* Quick Demo Prompts */}
            <Text style={styles.sectionLabel}>Tap a demo prompt:</Text>
            <View style={styles.chipRow}>
              {EXAMPLE_PROMPTS.map((prompt) => (
                <TouchableOpacity
                  key={prompt}
                  style={[styles.chip, prompt.includes('Aaj kaisa raha') && styles.insightChip]}
                  onPress={() => handlePromptPress(prompt)}
                >
                  {prompt.includes('Aaj kaisa raha') && (
                    <Ionicons name="sparkles" size={13} color="#ffffff" style={{ marginRight: 4 }} />
                  )}
                  <Text style={[styles.chipText, prompt.includes('Aaj kaisa raha') && styles.insightChipText]}>
                    {prompt}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {loading && <ActivityIndicator size="small" color="#0f3460" style={{ marginVertical: 8 }} />}

            {/* ── End-to-End "Aaj Kaisa Raha?" Brief Card ──────────────── */}
            {insightsBrief && (
              <View style={styles.briefCard}>
                <View style={styles.briefHeader}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Ionicons name="bar-chart" size={18} color="#0f3460" style={{ marginRight: 6 }} />
                    <Text style={styles.briefTitle}>Business Brief · Kirana Persona</Text>
                  </View>
                  <TouchableOpacity onPress={() => setInsightsBrief(null)}>
                    <Ionicons name="close-circle-outline" size={20} color="#6c757d" />
                  </TouchableOpacity>
                </View>

                {/* Synthetic Warning inside brief */}
                <View style={styles.briefSyntheticBanner}>
                  <Text style={styles.briefSyntheticText}>
                    ⚠ SYNTHETIC DATA — Derived from deterministic test fixture. Not Paytm data.
                  </Text>
                </View>

                {/* Comparison Period */}
                <View style={styles.periodBox}>
                  <Text style={styles.periodTitle}>Comparison Window:</Text>
                  <Text style={styles.periodText}>
                    Active: {formatPeriodDate(insightsBrief.period.start, insightsBrief.period.timezone)} to {formatPeriodDate(insightsBrief.period.end, insightsBrief.period.timezone, true)}
                  </Text>
                  <Text style={styles.periodSub}>
                    Compared against preceding 7-day period (Observational only)
                  </Text>
                </View>

                {/* Facts List */}
                <Text style={styles.factsTitle}>Key Facts (Provenance-Backed):</Text>
                {insightsBrief.facts.map((fact) => (
                  <View key={fact.id} style={styles.factRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.factLabel}>{fact.label}</Text>
                      <Text style={styles.factMeta}>
                        Source: {fact.source} · ID: {fact.id}
                      </Text>
                      {formatFactDefinition(fact) && <Text style={styles.factMeta}>{formatFactDefinition(fact)}</Text>}
                    </View>
                    <View style={{ alignItems: 'flex-end' }}>
                      <Text style={styles.factValue}>
                        {formatFactValue(fact)}
                      </Text>
                      {formatFactComparison(fact) && <Text style={styles.comparisonText}>{formatFactComparison(fact)}</Text>}
                    </View>
                  </View>
                ))}

                {/* Caveats */}
                <View style={styles.briefCaveatsBox}>
                  <Text style={styles.briefCaveatsTitle}>Caveats & Limitations:</Text>
                  {insightsBrief.caveats.map((c, idx) => (
                    <Text key={idx} style={styles.briefCaveatItem}>• {c}</Text>
                  ))}
                  <Text style={styles.briefCaveatItem}>
                    • Differences between periods are strictly observational and do not imply causal revenue impact.
                  </Text>
                </View>

                {/* Clearly Mocked Offer Action */}
                <View style={styles.mockActionCard}>
                  <View style={styles.mockActionHeader}>
                    <Text style={styles.mockActionTitle}>Proposed Merchant Action (Mock)</Text>
                    <View style={styles.mockBadge}>
                      <Text style={styles.mockBadgeText}>MOCK ONLY</Text>
                    </View>
                  </View>
                  <Text style={styles.mockActionDesc}>
                    Optional shop-side experiment. UPI trends cannot identify which products are slow-moving; choose the item and offer yourself:
                  </Text>
                  <TextInput
                    style={styles.mockActionInput}
                    value={mockOfferText}
                    onChangeText={setMockOfferText}
                  />

                  {mockOfferApproved ? (
                    <View style={styles.approvedBanner}>
                      <Ionicons name="checkmark-done-circle" size={18} color="#155724" style={{ marginRight: 6 }} />
                      <Text style={styles.approvedBannerText}>
                        Approved by Merchant (Mock only — NOT published to live customers).
                      </Text>
                    </View>
                  ) : (
                    <TouchableOpacity
                      style={styles.approveBtn}
                      onPress={() => setMockOfferApproved(true)}
                    >
                      <Ionicons name="hand-right-outline" size={16} color="#ffffff" style={{ marginRight: 6 }} />
                      <Text style={styles.approveBtnText}>Approve Mocked Counter Notice</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            )}

            {/* Customer Quick Card */}
            <View style={styles.customerCard}>
              <View style={styles.customerCardHeader}>
                <View>
                  <Text style={styles.customerCardTitle}>{customerName}</Text>
                  <Text style={styles.customerCardSub}>
                    {activeCustomerId ? `ID: ${activeCustomerId}` : 'Alias: Raju / Raju bhai'}
                  </Text>
                </View>
                {customerBalance !== null && (
                  <View style={styles.balanceTag}>
                    <Text style={styles.balanceLabel}>Due:</Text>
                    <Text style={styles.balanceAmount}>₹{(customerBalance / 100).toFixed(2)}</Text>
                  </View>
                )}
              </View>

              <View style={styles.quickActionRow}>
                <TouchableOpacity
                  style={styles.quickActionBtn}
                  onPress={handleCheckRajuBalance}
                  disabled={loading}
                >
                  <Ionicons name="wallet-outline" size={14} color="#0f3460" style={{ marginRight: 4 }} />
                  <Text style={styles.quickActionText}>Check Balance</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.quickActionBtn, styles.creditBtn]}
                  onPress={handleQuickCredit}
                  disabled={loading}
                >
                  <Ionicons name="add-circle-outline" size={14} color="#dc3545" style={{ marginRight: 4 }} />
                  <Text style={[styles.quickActionText, { color: '#dc3545' }]}>+₹50 Udhaar</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.quickActionBtn, styles.repayBtn]}
                  onPress={handleQuickRepayment}
                  disabled={loading}
                >
                  <Ionicons name="checkmark-circle-outline" size={14} color="#28a745" style={{ marginRight: 4 }} />
                  <Text style={[styles.quickActionText, { color: '#28a745' }]}>-₹30 Jamma</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Local Command Log */}
            {history.length > 0 && (
              <>
                <Text style={styles.sectionLabel}>Logged Utterances:</Text>
                {history.map((entry) => (
                  <View key={entry.id} style={styles.historyCard}>
                    <Text style={styles.historyText}>"{entry.text}"</Text>
                    <Text style={styles.historyTime}>{entry.timestamp}</Text>
                  </View>
                ))}
              </>
            )}
          </ScrollView>

          {/* Bottom Command Input */}
          <View style={styles.inputBar}>
            <TextInput
              style={styles.textInput}
              value={input}
              onChangeText={setInput}
              placeholder="Ask 'Aaj kaisa raha?' or type command..."
              placeholderTextColor="#9aa0a6"
              returnKeyType="send"
              onSubmitEditing={handleSubmitText}
            />
            <TouchableOpacity
              style={[styles.sendBtn, !input.trim() && styles.sendBtnDisabled]}
              onPress={handleSubmitText}
              disabled={!input.trim()}
            >
              <Ionicons name="send" size={18} color="#ffffff" />
            </TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#ffffff' },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#dee2e6',
    backgroundColor: '#ffffff',
  },
  appName: { fontSize: 22, fontWeight: '800', color: '#0f3460' },
  tagline: { fontSize: 11, color: '#6c757d' },
  syntheticBadge: {
    backgroundColor: '#fff3cd',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#ffc107',
  },
  syntheticBadgeText: { fontSize: 10, fontWeight: '700', color: '#856404' },
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#dee2e6',
    backgroundColor: '#f8f9fa',
  },
  tabItem: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabItemActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#0f3460',
    backgroundColor: '#ffffff',
  },
  tabLabel: { fontSize: 10, color: '#6c757d', marginTop: 2, fontWeight: '500' },
  tabLabelActive: { color: '#0f3460', fontWeight: '700' },
  copilotContainer: { flex: 1, backgroundColor: '#f8f9fa' },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 16 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6c757d',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#0f3460',
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipText: { fontSize: 12, color: '#0f3460' },
  insightChip: {
    backgroundColor: '#0f3460',
    borderColor: '#0f3460',
  },
  insightChipText: { color: '#ffffff', fontWeight: '700' },

  // ── "Aaj kaisa raha?" Brief Card
  briefCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    borderWidth: 2,
    borderColor: '#0f3460',
    elevation: 3,
  },
  briefHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  briefTitle: { fontSize: 16, fontWeight: '800', color: '#0f3460' },
  briefSyntheticBanner: {
    backgroundColor: '#fff3cd',
    padding: 8,
    borderRadius: 6,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#ffc107',
  },
  briefSyntheticText: { fontSize: 11, fontWeight: '700', color: '#856404', textAlign: 'center' },
  periodBox: {
    backgroundColor: '#e8f0fe',
    padding: 8,
    borderRadius: 6,
    marginBottom: 10,
  },
  periodTitle: { fontSize: 11, fontWeight: '700', color: '#0f3460' },
  periodText: { fontSize: 12, color: '#0f3460', fontFamily: 'monospace', marginTop: 2 },
  periodSub: { fontSize: 10, color: '#6c757d', fontStyle: 'italic', marginTop: 2 },
  factsTitle: { fontSize: 12, fontWeight: '700', color: '#495057', marginBottom: 6 },
  factRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f3f5',
  },
  factLabel: { fontSize: 13, fontWeight: '600', color: '#212529' },
  factMeta: { fontSize: 10, color: '#9aa0a6' },
  factValue: { fontSize: 15, fontWeight: '800', color: '#0f3460' },
  comparisonText: { fontSize: 11, color: '#6c757d' },
  briefCaveatsBox: {
    backgroundColor: '#f8f9fa',
    padding: 10,
    borderRadius: 6,
    marginTop: 10,
    marginBottom: 12,
  },
  briefCaveatsTitle: { fontSize: 11, fontWeight: '700', color: '#495057', marginBottom: 4 },
  briefCaveatItem: { fontSize: 11, color: '#6c757d', lineHeight: 15, marginBottom: 2 },
  mockActionCard: {
    backgroundColor: '#fbfbfb',
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 6,
    padding: 12,
  },
  mockActionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  mockActionTitle: { fontSize: 13, fontWeight: '700', color: '#0f3460' },
  mockBadge: { backgroundColor: '#e2e3e5', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  mockBadgeText: { fontSize: 9, fontWeight: '700', color: '#383d41' },
  mockActionDesc: { fontSize: 11, color: '#6c757d', marginBottom: 6 },
  mockActionInput: {
    height: 36,
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 4,
    paddingHorizontal: 8,
    fontSize: 12,
    backgroundColor: '#ffffff',
    marginBottom: 8,
  },
  approveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0f3460',
    paddingVertical: 8,
    borderRadius: 4,
  },
  approveBtnText: { color: '#ffffff', fontSize: 12, fontWeight: '700' },
  approvedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#d4edda',
    padding: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#c3e6cb',
  },
  approvedBannerText: { fontSize: 11, fontWeight: '700', color: '#155724', flex: 1 },

  // Customer Card
  customerCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#dee2e6',
    elevation: 1,
  },
  customerCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  customerCardTitle: { fontSize: 16, fontWeight: '700', color: '#0f3460' },
  customerCardSub: { fontSize: 11, color: '#6c757d', marginTop: 1 },
  balanceTag: {
    backgroundColor: '#fff3cd',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    alignItems: 'flex-end',
  },
  balanceLabel: { fontSize: 10, color: '#856404', fontWeight: '600' },
  balanceAmount: { fontSize: 16, fontWeight: '800', color: '#856404' },
  quickActionRow: { flexDirection: 'row', gap: 6 },
  quickActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#e8f0fe',
    paddingVertical: 8,
    borderRadius: 6,
  },
  creditBtn: { backgroundColor: '#fff5f5' },
  repayBtn: { backgroundColor: '#eef9f0' },
  quickActionText: { fontSize: 12, fontWeight: '600', color: '#0f3460' },
  historyCard: {
    backgroundColor: '#ffffff',
    borderRadius: 6,
    padding: 10,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#0f3460',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  historyText: { fontSize: 13, color: '#212529', flex: 1 },
  historyTime: { fontSize: 11, color: '#9aa0a6', marginLeft: 8 },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#dee2e6',
    backgroundColor: '#ffffff',
  },
  textInput: {
    flex: 1,
    height: 40,
    backgroundColor: '#f8f9fa',
    borderRadius: 20,
    paddingHorizontal: 14,
    fontSize: 13,
    color: '#212529',
    borderWidth: 1,
    borderColor: '#dee2e6',
    marginRight: 8,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#0f3460',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: { backgroundColor: '#adb5bd' },
});
