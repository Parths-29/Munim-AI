/**
 * HomeScreen — KiranaOS / Munim-AI Mobile Hub
 *
 * Provides tabbed navigation across:
 * 1. Copilot (bounded text commands, credit/repayment, customer resolve, derived balance,
 *    and end-to-end "Aaj kaisa raha?" insights brief slice with AI explanation)
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
 * - AI explanation is server-side, facts-only validated with deterministic fallback.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
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
import { AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import * as FileSystem from 'expo-file-system/legacy';
import { InfoBanner, SyntheticDataPill } from '@/components/InfoBanner';
import {
  resolveCustomer,
  createCustomer,
  fetchCustomerBalance,
  postCredit,
  postRepayment,
  resolveProduct,
  fetchProductStock,
  recordStockoutObservation,
  recordPhysicalCount,
  fetchActivitySummary,
  Customer,
  Product,
  fetchInsightFacts,
  fetchBriefExplanation,
  approveMockAction,
  fetchLatestMockAction,
  transcribeMerchantAudio,
  interpretMerchantCommand,
  FactsResponse,
  BriefExplanationResponse,
  MockActionResponse,
  ActivitySummaryResponse,
} from '@/api/ledgerClient';
import { MerchantCommandIntent, parseMerchantCommand } from '@/features/home/parseMerchantCommand';
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

interface PendingCommand {
  commandId: string;
  sourceChannel: 'text' | 'voice';
  intent: MerchantCommandIntent;
  entityQuery: string;
  amountPaise?: number;
  customer?: Customer;
  matches?: Customer[];
  product?: Product;
  productMatches?: Product[];
  currentBalancePaise?: number;
  currentStockQuantity?: number;
  stockUnit?: string;
  countedQuantity?: number;
  sourceUtterance?: string;
  createCustomerOnConfirm: boolean;
}

interface CommandFeedback {
  tone: 'info' | 'success' | 'error';
  title: string;
  message: string;
}

function formatRupees(amountPaise: number): string {
  return `₹${(amountPaise / 100).toFixed(2)}`;
}

const EXAMPLE_PROMPTS = [
  'Aaj kaisa raha?',
  'Raju bhai ka balance batao',
  'Add new customer Rajju Sharma',
  'How many Maggi packs are left?',
  'Set Maggi stock count to 10 packs',
  'Summarize today’s payments',
  'What happened in the shop today?',
  'Raju bhai ka ₹50 udhaar likh do',
  'Raju bhai ka ₹300 jamma kar lo',
  'Maggi khatam ho gaya',
];

export default function HomeScreen() {
  const [activeTab, setActiveTab] = useState<Tab>('copilot');

  // Copilot text state
  const [input, setInput] = useState('');
  const [inputSourceChannel, setInputSourceChannel] = useState<'text' | 'voice'>('text');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCustomerId, setActiveCustomerId] = useState<string | null>(null);
  const [customerName, setCustomerName] = useState('Raju bhai');
  const [customerBalance, setCustomerBalance] = useState<number | null>(null);
  const [pendingCommand, setPendingCommand] = useState<PendingCommand | null>(null);
  const [commandFeedback, setCommandFeedback] = useState<CommandFeedback | null>(null);
  const commandBusyRef = useRef(false);

  // "Aaj kaisa raha?" end-to-end slice state
  const [insightsBrief, setInsightsBrief] = useState<FactsResponse | null>(null);
  const [aiExplanation, setAiExplanation] = useState<BriefExplanationResponse | null>(null);
  const [mockAction, setMockAction] = useState<MockActionResponse | null>(null);
  const [mockActionDraft, setMockActionDraft] = useState('');
  const approvalKeyRef = useRef<string | null>(null);
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(audioRecorder);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState('Mic audio is sent to Sarvam for transcription. Munim does not retain the recording; review the transcript before sending.');
  const voiceStopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (voiceStopTimerRef.current) clearTimeout(voiceStopTimerRef.current);
  }, []);

  // Trigger "Aaj kaisa raha?" insight slice + AI explanation
  const handleLoadInsightsBrief = useCallback(async () => {
    setLoading(true);
    try {
      const [factsData, explanationData, latestAction] = await Promise.all([
        fetchInsightFacts('kirana'),
        fetchBriefExplanation('kirana').catch(() => null),
        fetchLatestMockAction('kirana').catch(() => null),
      ]);
      setInsightsBrief(factsData);
      setAiExplanation(explanationData);
      setMockAction(latestAction);
      setMockActionDraft(
        latestAction?.action_text ?? explanationData?.proposed_action ??
          'Put up a counter notice inviting shoppers to ask about current in-store offers. Demo only; not published.',
      );
      approvalKeyRef.current = null;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Could Not Load Business Brief', `${message}\nEnsure backend is running at ${process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleApproveMockAction = async () => {
    if (loading) return;
    const actionText = mockActionDraft.trim();
    if (!actionText) {
      Alert.alert('Action Text Required', 'Write the counter notice or shop-side action you want to track.');
      return;
    }
    if (!approvalKeyRef.current) approvalKeyRef.current = `mock_action_${Date.now()}`;
    setLoading(true);
    try {
      const approved = await approveMockAction({
        persona: 'kirana',
        action_type: aiExplanation?.action_type ?? 'counter_notice',
        action_text: actionText,
        confirmed: true,
        idempotency_key: approvalKeyRef.current,
      });
      setMockAction(approved);
      setMockActionDraft(approved.action_text);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Could Not Record Mock Approval', message);
    } finally {
      setLoading(false);
    }
  };

  const stopVoiceRecording = async () => {
    if (voiceStopTimerRef.current) {
      clearTimeout(voiceStopTimerRef.current);
      voiceStopTimerRef.current = null;
    }
    setVoiceBusy(true);
    setVoiceNotice('Transcribing your short recording…');
    try {
      await audioRecorder.stop();
      const uri = audioRecorder.uri;
      if (!uri) throw new Error('No audio file was created. Please try again.');
      const result = await transcribeMerchantAudio(uri);
      if (!result.transcript.trim()) throw new Error('No speech was detected. Please try again or type the request.');
      setInput(result.transcript.trim());
      setInputSourceChannel('voice');
      const detectedLanguage = result.language_code ? ` (${result.language_code})` : '';
      setVoiceNotice(`Transcript ready${detectedLanguage}. Review it, then tap send. Nothing is recorded until you confirm the next preview.`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setVoiceNotice(`Voice transcription failed: ${message} You can type the request instead.`);
      Alert.alert('Voice Input Unavailable', message);
    } finally {
      const uri = audioRecorder.uri;
      if (uri?.startsWith('blob:')) URL.revokeObjectURL(uri);
      else if (uri) await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => undefined);
      setVoiceBusy(false);
    }
  };

  const startVoiceRecording = async () => {
    if (loading || voiceBusy || recorderState.isRecording) return;
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setVoiceNotice('Microphone permission was denied. Allow microphone access for this site, then try again.');
        Alert.alert('Microphone Permission Needed', 'Allow microphone access to dictate a short merchant request.');
        return;
      }
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
      setVoiceNotice('Recording… tap the microphone to stop. Maximum 20 seconds.');
      voiceStopTimerRef.current = setTimeout(() => { void stopVoiceRecording(); }, 20_000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setVoiceNotice(`Could not start microphone recording: ${message} Type your request instead.`);
      Alert.alert('Could Not Start Recording', message);
    }
  };

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

  // Quick Action: Repayment ₹300 (matches the PRD's Raju demo arithmetic)
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
        amount_paise: 30000,
        source_event_id: `evt_repay_${Date.now()}`,
        idempotency_key: `cmd_repay_${Date.now()}`,
        confirmed: true,
      });
      const bal = await fetchCustomerBalance(custId);
      setCustomerBalance(bal.balance_due_paise);
      Alert.alert(
        'Repayment Posted Successfully',
        `₹300.00 repayment posted for ${customerName}.\nRemaining Balance: ₹${(bal.balance_due_paise / 100).toFixed(2)}\nEntry ID: ${repayRes.entry_id}`
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
    setInputSourceChannel('text');
    if (prompt.toLowerCase().includes('aaj kaisa raha')) {
      handleLoadInsightsBrief();
    }
  };

  const handleRunMerchantCommand = async (utterance: string, sourceChannel: 'text' | 'voice' = 'text') => {
    let parsed = parseMerchantCommand(utterance);
    setPendingCommand(null);
    setCommandFeedback(null);

    let aiAssisted = false;
    if (parsed.status === 'unsupported') {
      if (commandBusyRef.current) return;
      commandBusyRef.current = true;
      setLoading(true);
      try {
        const interpretation = await interpretMerchantCommand(utterance, sourceChannel);
        if (interpretation.status === 'ready' && interpretation.intent) {
          // Re-parse a canonical command with the existing deterministic parser.
          // This keeps currency conversion and all confirmation rules in one path.
          const entity = interpretation.entity_text ?? '';
          const canonical = interpretation.intent === 'credit'
            ? `${entity} ${interpretation.amount_text ?? ''} udhaar`
            : interpretation.intent === 'repayment'
              ? `${entity} ${interpretation.amount_text ?? ''} jama`
              : interpretation.intent === 'balance'
                ? `${entity} balance`
                : interpretation.intent === 'customer_create'
                  ? `add new customer ${entity}`
                  : interpretation.intent === 'stockout'
                    ? `${entity} khatam`
                    : interpretation.intent === 'stock_check'
                      ? `check stock of ${entity}`
                      : interpretation.intent === 'stock_count'
                        ? `set ${entity} stock count to ${interpretation.count_text ?? ''}`
                        : interpretation.intent === 'payment_summary'
                          ? 'payment summary'
                          : 'summarize shop activity';
          const candidate = parseMerchantCommand(canonical);
          if (candidate.status === 'ready' && candidate.intent === interpretation.intent) {
            parsed = candidate;
            aiAssisted = true;
          } else {
            parsed = {
              status: 'clarification',
              message: 'AI understood the request, but the amount or action did not pass local validation. Please rephrase it with one explicit amount.',
            };
          }
        } else if (interpretation.status === 'clarification' || interpretation.status === 'unavailable') {
          parsed = {
            status: 'clarification',
            message: interpretation.message ?? 'Please use a supported command format or clarify the request.',
          };
        }
      } catch {
        // Preserve the existing deterministic parser behavior when the NLP service is offline.
      }
    }

    if (parsed.status !== 'ready') {
      setCommandFeedback({
        tone: parsed.status === 'unsupported' ? 'info' : 'error',
        title: parsed.status === 'unsupported' ? 'Command Not Supported Yet' : 'Please Clarify',
        message: parsed.message,
      });
      if (commandBusyRef.current) {
        commandBusyRef.current = false;
        setLoading(false);
      }
      return;
    }

    if (!commandBusyRef.current) {
      commandBusyRef.current = true;
      setLoading(true);
    }
    const commandId = `cmd_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    try {
      if (parsed.intent === 'payment_summary' || parsed.intent === 'timeline_summary') {
        const summary = await fetchActivitySummary();
        const message = parsed.intent === 'payment_summary'
          ? `Mock payment feed: ${summary.successful_payment_count} successful totaling ${formatRupees(summary.successful_payment_total_paise)}, ${summary.open_review_payment_count} waiting for review totaling ${formatRupees(summary.open_review_payment_total_paise)}, ${summary.pending_payment_count} pending, ${summary.failed_payment_count} failed, and ${summary.reversed_payment_count} reversed. Ledger repayments actually posted: ${summary.repayment_entry_count} totaling ${formatRupees(summary.repayment_total_paise)}. Latest events: ${summary.recent_payments.slice(0, 3).map((payment) => `${payment.payment_status} ${formatRupees(payment.amount_paise)} (${payment.resolution_status.toLowerCase().replace(/_/g, ' ')})`).join('; ') || 'none recorded'}. All recorded synthetic demo history; not live UPI.`
          : `${summary.summary_text} Recent activity: ${summary.latest_events.slice(0, 3).map((event) => event.summary).join(' ')} All figures are synthetic demo records.`;
        setCommandFeedback({
          tone: 'success',
          title: parsed.intent === 'payment_summary' ? 'Payment Summary · Synthetic Demo' : 'Shop Activity Summary · Synthetic Demo',
          message,
        });
        return;
      }

      if (parsed.intent === 'customer_create') {
        const resolution = await resolveCustomer(parsed.customerName);
        if (resolution.status === 'AMBIGUOUS') {
          setPendingCommand({
            commandId,
            sourceChannel,
            intent: 'customer_create',
            entityQuery: parsed.customerName,
            matches: resolution.matches,
            sourceUtterance: utterance,
            createCustomerOnConfirm: false,
          });
          setCommandFeedback({ tone: 'info', title: 'Customer Name Already Matches Multiple Records', message: 'Choose a matching record to avoid creating a duplicate.' });
          return;
        }
        if (resolution.status === 'RESOLVED') {
          setCommandFeedback({ tone: 'info', title: 'Customer Already Exists', message: `${resolution.matches[0].display_name} already exists. No duplicate was created.` });
          return;
        }
        setPendingCommand({
          commandId,
          sourceChannel,
          intent: 'customer_create',
          entityQuery: parsed.customerName,
          sourceUtterance: utterance,
          createCustomerOnConfirm: true,
        });
        setCommandFeedback({ tone: 'info', title: 'New Customer Preview', message: 'Review the transcribed name carefully. Confirming adds this exact customer; it does not create a credit entry.' });
        return;
      }

      if (parsed.intent === 'stockout' || parsed.intent === 'stock_check' || parsed.intent === 'stock_count') {
        const productResolution = await resolveProduct(parsed.productQuery);
        if (productResolution.status === 'AMBIGUOUS') {
          setPendingCommand({
            commandId,
            sourceChannel,
            intent: parsed.intent,
            entityQuery: parsed.productQuery,
            productMatches: productResolution.matches,
            countedQuantity: parsed.intent === 'stock_count' ? parsed.countedQuantity : undefined,
            sourceUtterance: utterance,
            createCustomerOnConfirm: false,
          });
          setCommandFeedback({
            tone: 'info',
            title: 'Choose the Exact Product',
            message: 'I found more than one exact product alias. Choose one before checking or changing stock.',
          });
          return;
        }
        if (productResolution.status === 'NOT_FOUND') {
          setCommandFeedback({
            tone: 'error',
            title: 'Product Not Found',
            message: `No exact product match for “${parsed.productQuery}”. Nothing was recorded. Add or resolve the product first.`,
          });
          return;
        }

        const product = productResolution.matches[0];
        const stock = await fetchProductStock(product.product_id);
        if (parsed.intent === 'stock_check') {
          setCommandFeedback({
            tone: 'success',
            title: `Current Stock · ${product.name}`,
            message: `${stock.on_hand_quantity} ${stock.unit}${stock.on_hand_quantity === 1 ? '' : 's'} on hand. This is the latest recorded physical count, not a live sensor reading.`,
          });
          return;
        }
        setPendingCommand({
          commandId,
          sourceChannel,
          intent: parsed.intent,
          entityQuery: parsed.productQuery,
          product,
          countedQuantity: parsed.intent === 'stock_count' ? parsed.countedQuantity : undefined,
          currentStockQuantity: stock.on_hand_quantity,
          stockUnit: stock.unit,
          sourceUtterance: utterance,
          createCustomerOnConfirm: false,
        });
        setCommandFeedback(parsed.intent === 'stockout'
          ? { tone: 'info', title: 'Stockout Observation Preview', message: 'Confirming records what you observed. It does not change the on-hand count.' }
          : { tone: 'info', title: 'Physical Count Preview', message: 'Review the product and counted quantity. Stock changes only after you confirm.' });
        return;
      }

      const resolution = await resolveCustomer(parsed.customerQuery);
      if (resolution.status === 'AMBIGUOUS') {
        setPendingCommand({
          commandId,
          sourceChannel,
          intent: parsed.intent,
          entityQuery: parsed.customerQuery,
          amountPaise: 'amountPaise' in parsed ? parsed.amountPaise : undefined,
          matches: resolution.matches,
          sourceUtterance: utterance,
          createCustomerOnConfirm: false,
        });
        setCommandFeedback({
          tone: 'info',
          title: 'Choose the Exact Customer',
          message: 'I found more than one exact alias match. Choose the customer before any balance lookup or ledger write.',
        });
        return;
      }

      if (resolution.status === 'NOT_FOUND') {
        if (parsed.intent === 'credit') {
          setPendingCommand({
            commandId,
            sourceChannel,
            intent: parsed.intent,
            entityQuery: parsed.customerQuery,
            amountPaise: parsed.amountPaise,
            currentBalancePaise: 0,
            sourceUtterance: utterance,
            createCustomerOnConfirm: true,
          });
          setCommandFeedback({
            tone: 'info',
            title: 'New Customer Preview',
            message: 'No exact customer match exists. Confirming will create this customer and then post the credit.',
          });
        } else {
          setCommandFeedback({
            tone: 'error',
            title: 'Customer Not Found',
            message: `No exact match for “${parsed.customerQuery}”. Nothing was recorded. Add or resolve the customer first.`,
          });
        }
        return;
      }

      const customer = resolution.matches[0];
      const balance = await fetchCustomerBalance(customer.customer_id);
      setCustomerName(customer.display_name);
      setActiveCustomerId(customer.customer_id);
      setCustomerBalance(balance.balance_due_paise);

      if (parsed.intent === 'balance') {
        setCommandFeedback({
          tone: 'success',
          title: `Balance for ${customer.display_name}`,
          message: `${formatRupees(balance.balance_due_paise)} due across ${balance.entry_count} posted ledger entries.`,
        });
        return;
      }

      setPendingCommand({
        commandId,
        sourceChannel,
        intent: parsed.intent,
        entityQuery: parsed.customerQuery,
        amountPaise: parsed.amountPaise,
        customer,
        currentBalancePaise: balance.balance_due_paise,
        sourceUtterance: utterance,
        createCustomerOnConfirm: false,
      });
      setCommandFeedback({
        tone: 'info',
        title: 'Review Before Recording',
        message: aiAssisted
          ? 'AI-assisted draft. Check the exact customer and amount; the ledger will not change until you confirm.'
          : 'This is a text-parser draft. Check the customer and amount; the ledger will not change until you confirm.',
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setCommandFeedback({
        tone: 'error',
        title: 'Could Not Prepare Command',
        message: `${message} Nothing was recorded.`,
      });
    } finally {
      commandBusyRef.current = false;
      setLoading(false);
    }
  };

  const handleChooseCommandCustomer = async (customer: Customer) => {
    if (!pendingCommand || commandBusyRef.current) return;
    const command = pendingCommand;
    commandBusyRef.current = true;
    setLoading(true);
    setCommandFeedback(null);
    try {
      if (command.intent === 'customer_create') {
        setPendingCommand(null);
        setCommandFeedback({
          tone: 'info',
          title: 'Customer Already Exists',
          message: `Selected ${customer.display_name}. No duplicate was created.`,
        });
        return;
      }
      const balance = await fetchCustomerBalance(customer.customer_id);
      setCustomerName(customer.display_name);
      setActiveCustomerId(customer.customer_id);
      setCustomerBalance(balance.balance_due_paise);

      if (command.intent === 'balance') {
        setPendingCommand(null);
        setCommandFeedback({
          tone: 'success',
          title: `Balance for ${customer.display_name}`,
          message: `${formatRupees(balance.balance_due_paise)} due across ${balance.entry_count} posted ledger entries.`,
        });
      } else {
        setPendingCommand({
          ...command,
          customer,
          matches: undefined,
          currentBalancePaise: balance.balance_due_paise,
        });
        setCommandFeedback({
          tone: 'info',
          title: 'Review Before Recording',
          message: `Selected ${customer.display_name}. Confirm only if this is the right customer and amount.`,
        });
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setCommandFeedback({ tone: 'error', title: 'Could Not Load Balance', message });
    } finally {
      commandBusyRef.current = false;
      setLoading(false);
    }
  };

  const handleChooseCommandProduct = async (product: Product) => {
    if (!pendingCommand || !['stockout', 'stock_check', 'stock_count'].includes(pendingCommand.intent) || commandBusyRef.current) return;
    const command = pendingCommand;
    commandBusyRef.current = true;
    setLoading(true);
    setCommandFeedback(null);
    try {
      const stock = await fetchProductStock(product.product_id);
      if (command.intent === 'stock_check') {
        setPendingCommand(null);
        setCommandFeedback({
          tone: 'success',
          title: `Current Stock · ${product.name}`,
          message: `${stock.on_hand_quantity} ${stock.unit}${stock.on_hand_quantity === 1 ? '' : 's'} on hand. This is the latest recorded physical count, not a live sensor reading.`,
        });
        return;
      }
      setPendingCommand({
        ...command,
        product,
        productMatches: undefined,
        currentStockQuantity: stock.on_hand_quantity,
        stockUnit: stock.unit,
      });
      setCommandFeedback({
        tone: 'info',
        title: command.intent === 'stockout' ? 'Stockout Observation Preview' : 'Physical Count Preview',
        message: command.intent === 'stockout'
          ? `Selected ${product.name}. Confirm only if this is the right product. The on-hand count will stay unchanged.`
          : `Selected ${product.name}. Review the counted quantity before changing on-hand stock.`,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setCommandFeedback({ tone: 'error', title: 'Could Not Load Product Stock', message });
    } finally {
      commandBusyRef.current = false;
      setLoading(false);
    }
  };

  const handleConfirmCommand = async () => {
    if (!pendingCommand || pendingCommand.matches?.length || pendingCommand.productMatches?.length || commandBusyRef.current) return;
    const command = pendingCommand;
    if (command.intent === 'stockout') {
      if (!command.product) return;
      commandBusyRef.current = true;
      setLoading(true);
      setCommandFeedback(null);
      try {
        const result = await recordStockoutObservation({
          product_id: command.product.product_id,
          source_event_id: `event_${command.commandId}`,
          idempotency_key: `stockout_${command.commandId}`,
          confirmed: true,
          source_utterance: command.sourceUtterance,
          source_channel: command.sourceChannel,
        });
        setPendingCommand(null);
        setCommandFeedback({
          tone: 'success',
          title: 'Stockout Observation Recorded',
          message: `${command.product.name} is marked as reported out of stock. On-hand remains ${command.currentStockQuantity ?? 0} ${command.stockUnit ?? command.product.unit}; observation ${result.observation_id}.`,
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        setCommandFeedback({
          tone: 'error',
          title: 'Could Not Record Observation',
          message: `${message} The preview remains available; retrying uses the same idempotency key.`,
        });
      } finally {
        commandBusyRef.current = false;
        setLoading(false);
      }
      return;
    }

    if (command.intent === 'customer_create') {
      commandBusyRef.current = true;
      setLoading(true);
      setCommandFeedback(null);
      try {
        const created = await createCustomer({
          display_name: command.entityQuery,
          aliases: [command.entityQuery],
          confirmed: true,
          idempotency_key: `customer_${command.commandId}`,
          source_utterance: command.sourceUtterance,
          source_channel: command.sourceChannel,
        });
        setPendingCommand(null);
        setCommandFeedback({
          tone: 'success',
          title: 'Customer Added',
          message: `${created.display_name} was added with the exact transcribed name. No credit or repayment was recorded.`,
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        setCommandFeedback({ tone: 'error', title: 'Could Not Add Customer', message });
      } finally {
        commandBusyRef.current = false;
        setLoading(false);
      }
      return;
    }

    if (command.intent === 'stock_count') {
      if (!command.product || command.countedQuantity === undefined) return;
      commandBusyRef.current = true;
      setLoading(true);
      setCommandFeedback(null);
      try {
        const result = await recordPhysicalCount({
          product_id: command.product.product_id,
          counted_quantity: command.countedQuantity,
          source_event_id: `event_${command.commandId}`,
          idempotency_key: `stockcount_${command.commandId}`,
          confirmed: true,
          source_utterance: command.sourceUtterance,
          source_channel: command.sourceChannel,
        });
        setPendingCommand(null);
        setCommandFeedback({
          tone: 'success',
          title: 'Physical Count Recorded',
          message: `${command.product.name} is now recorded at ${result.counted_quantity} ${result.unit}${result.counted_quantity === 1 ? '' : 's'}. Change from prior count: ${result.quantity_delta >= 0 ? '+' : ''}${result.quantity_delta}.`,
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        setCommandFeedback({ tone: 'error', title: 'Could Not Record Count', message: `${message} The preview remains available; retrying uses the same idempotency key.` });
      } finally {
        commandBusyRef.current = false;
        setLoading(false);
      }
      return;
    }

    if (command.intent === 'stock_check') return;
    if (command.intent === 'balance' || command.amountPaise === undefined) return;

    const currentBalance = command.currentBalancePaise ?? 0;
    if (command.intent === 'repayment' && command.amountPaise > currentBalance) {
      setCommandFeedback({
        tone: 'error',
        title: 'Repayment Exceeds Balance',
        message: `Current due is ${formatRupees(currentBalance)}. This repayment cannot be posted. Nothing was recorded.`,
      });
      return;
    }

    commandBusyRef.current = true;
    setLoading(true);
    setCommandFeedback(null);
    try {
      const customer = command.customer ?? (command.createCustomerOnConfirm
        ? await createCustomer({
            display_name: command.entityQuery,
            aliases: [command.entityQuery],
            confirmed: true,
            idempotency_key: `customer_${command.commandId}`,
            source_utterance: command.sourceUtterance,
            source_channel: command.sourceChannel,
          })
        : null);
      if (!customer) throw new Error('Choose an exact customer before recording this command.');

      const request = {
        customer_id: customer.customer_id,
        amount_paise: command.amountPaise,
        source_event_id: `event_${command.commandId}`,
        idempotency_key: `ledger_${command.commandId}`,
        confirmed: true,
        source_utterance: command.sourceUtterance,
        source_channel: command.sourceChannel,
      };
      const result = command.intent === 'credit'
        ? await postCredit(request)
        : await postRepayment(request);
      const balance = await fetchCustomerBalance(customer.customer_id);

      setCustomerName(customer.display_name);
      setActiveCustomerId(customer.customer_id);
      setCustomerBalance(balance.balance_due_paise);
      setPendingCommand(null);
      setCommandFeedback({
        tone: 'success',
        title: command.intent === 'credit' ? 'Udhaar Recorded' : 'Jama Recorded',
        message: `${formatRupees(command.amountPaise)} ${command.intent === 'credit' ? 'credit' : 'repayment'} recorded for ${customer.display_name}. New due: ${formatRupees(balance.balance_due_paise)}. Entry: ${result.entry_id}.`,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setCommandFeedback({
        tone: 'error',
        title: 'Could Not Record Command',
        message: `${message} The preview remains available; retrying uses the same idempotency key.`,
      });
    } finally {
      commandBusyRef.current = false;
      setLoading(false);
    }
  };

  const handleSubmitText = useCallback(async () => {
    if (loading || commandBusyRef.current) return;
    const trimmed = input.trim();
    if (!trimmed) return;

    const normalizedInput = trimmed.toLowerCase();
    const isInsight = /kaisa raha|how was business|business brief|show insights/.test(normalizedInput);
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
    setInputSourceChannel('text');
    setCommandFeedback(null);
    setPendingCommand(null);

    if (isInsight) {
      handleLoadInsightsBrief();
      return;
    }
    await handleRunMerchantCommand(trimmed, inputSourceChannel);
  }, [input, inputSourceChannel, loading, handleLoadInsightsBrief, handleRunMerchantCommand]);

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

            <InfoBanner text="Voice transcripts use Sarvam when configured and always go through merchant review. Live Paytm servers are not connected." />

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

            {commandFeedback && (
              <View style={[
                styles.commandFeedback,
                commandFeedback.tone === 'success'
                  ? styles.commandFeedback_success
                  : commandFeedback.tone === 'error'
                    ? styles.commandFeedback_error
                    : styles.commandFeedback_info,
              ]}>
                <Text style={styles.commandFeedbackTitle}>{commandFeedback.title}</Text>
                <Text style={styles.commandFeedbackText}>{commandFeedback.message}</Text>
              </View>
            )}

            {pendingCommand && (
              <View style={styles.commandPreviewCard}>
                <View style={styles.commandPreviewHeader}>
                  <Text style={styles.commandPreviewTitle}>
                    {pendingCommand.intent === 'credit'
                      ? 'Udhaar Preview'
                      : pendingCommand.intent === 'repayment'
                        ? 'Jama Preview'
                        : pendingCommand.intent === 'stockout'
                          ? 'Stockout Preview'
                          : pendingCommand.intent === 'stock_check'
                            ? 'Stock Lookup'
                            : pendingCommand.intent === 'stock_count'
                              ? 'Physical Count Preview'
                              : pendingCommand.intent === 'customer_create'
                                ? 'New Customer Preview'
                          : 'Choose Customer'}
                  </Text>
                  <View style={styles.commandNotSavedBadge}>
                    <Text style={styles.commandNotSavedText}>
                      {pendingCommand.intent === 'balance' || pendingCommand.intent === 'stock_check' ? 'READ ONLY' : 'NOT RECORDED'}
                    </Text>
                  </View>
                </View>

                {pendingCommand.matches?.length ? (
                  <>
                    <Text style={styles.commandPreviewText}>Which exact customer did you mean by “{pendingCommand.entityQuery}”?</Text>
                    {pendingCommand.matches.map((match) => (
                      <TouchableOpacity
                        key={match.customer_id}
                        style={styles.commandMatchButton}
                        onPress={() => handleChooseCommandCustomer(match)}
                        disabled={loading}
                      >
                        <Text style={styles.commandMatchName}>{match.display_name}</Text>
                        <Text style={styles.commandMatchId}>{match.customer_id}</Text>
                      </TouchableOpacity>
                    ))}
                    <TouchableOpacity
                      style={styles.commandCancelButton}
                      onPress={() => { setPendingCommand(null); setCommandFeedback({ tone: 'info', title: 'Cancelled', message: 'Nothing was recorded.' }); }}
                      disabled={loading}
                    >
                      <Text style={styles.commandCancelText}>Cancel command</Text>
                    </TouchableOpacity>
                  </>
                ) : pendingCommand.productMatches?.length ? (
                  <>
                    <Text style={styles.commandPreviewText}>Which exact product did you mean by “{pendingCommand.entityQuery}”?</Text>
                    {pendingCommand.productMatches.map((product) => (
                      <TouchableOpacity
                        key={product.product_id}
                        style={styles.commandMatchButton}
                        onPress={() => handleChooseCommandProduct(product)}
                        disabled={loading}
                      >
                        <Text style={styles.commandMatchName}>{product.name}</Text>
                        <Text style={styles.commandMatchId}>{product.product_id}</Text>
                      </TouchableOpacity>
                    ))}
                    <TouchableOpacity
                      style={styles.commandCancelButton}
                      onPress={() => { setPendingCommand(null); setCommandFeedback({ tone: 'info', title: 'Cancelled', message: 'Nothing was recorded.' }); }}
                      disabled={loading}
                    >
                      <Text style={styles.commandCancelText}>Cancel command</Text>
                    </TouchableOpacity>
                  </>
                ) : (
                  <>
                    <Text style={styles.commandPreviewText}>
                      {['stockout', 'stock_check', 'stock_count'].includes(pendingCommand.intent)
                        ? `Product: ${pendingCommand.product?.name ?? pendingCommand.entityQuery}`
                        : pendingCommand.intent === 'customer_create'
                          ? `New customer name: ${pendingCommand.entityQuery}`
                          : `Customer: ${pendingCommand.customer?.display_name ?? pendingCommand.entityQuery}`}
                    </Text>
                    {pendingCommand.amountPaise !== undefined && (
                      <Text style={styles.commandPreviewAmount}>
                        Amount: {formatRupees(pendingCommand.amountPaise)}
                      </Text>
                    )}
                    {pendingCommand.intent === 'stockout' && pendingCommand.currentStockQuantity !== undefined && (
                      <Text style={styles.commandPreviewText}>
                        Current on-hand: {pendingCommand.currentStockQuantity} {pendingCommand.stockUnit ?? pendingCommand.product?.unit}
                      </Text>
                    )}
                    {pendingCommand.intent === 'stockout' && (
                      <Text style={styles.commandPreviewNote}>This records an observation only. It will not change stock quantity; use a physical count to update on-hand.</Text>
                    )}
                    {pendingCommand.intent === 'stock_count' && pendingCommand.countedQuantity !== undefined && (
                      <>
                        <Text style={styles.commandPreviewText}>Current on-hand: {pendingCommand.currentStockQuantity ?? 0} {pendingCommand.stockUnit ?? pendingCommand.product?.unit}</Text>
                        <Text style={styles.commandPreviewAmount}>Counted quantity: {pendingCommand.countedQuantity}</Text>
                        <Text style={styles.commandPreviewNote}>This confirmed count changes the recorded on-hand quantity. Check the product and count before confirming.</Text>
                      </>
                    )}
                    {pendingCommand.currentBalancePaise !== undefined && pendingCommand.amountPaise !== undefined && (
                      <Text style={styles.commandPreviewText}>
                        Current due: {formatRupees(pendingCommand.currentBalancePaise)}
                        {pendingCommand.intent === 'credit'
                          ? ` · after recording: ${formatRupees(pendingCommand.currentBalancePaise + pendingCommand.amountPaise)}`
                          : ''}
                      </Text>
                    )}
                    {pendingCommand.createCustomerOnConfirm && (
                      <Text style={styles.commandPreviewNote}>
                        Confirming creates a new synthetic customer with this exact transcribed name. Review spelling carefully; no credit or repayment is included.
                      </Text>
                    )}
                    {pendingCommand.intent === 'repayment' &&
                      pendingCommand.amountPaise !== undefined &&
                      pendingCommand.currentBalancePaise !== undefined &&
                      pendingCommand.amountPaise > pendingCommand.currentBalancePaise && (
                        <Text style={styles.commandBlockedText}>
                          Amount exceeds the current due. Change the command; no repayment can be posted.
                        </Text>
                      )}
                    {pendingCommand.intent !== 'balance' && pendingCommand.intent !== 'stock_check' && (
                      <View style={styles.commandButtonRow}>
                        <TouchableOpacity
                          style={styles.commandCancelButton}
                          onPress={() => { setPendingCommand(null); setCommandFeedback({ tone: 'info', title: 'Cancelled', message: 'Nothing was recorded.' }); }}
                          disabled={loading}
                        >
                          <Text style={styles.commandCancelText}>Cancel</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={[
                            styles.commandConfirmButton,
                            (loading || (pendingCommand.intent === 'repayment' &&
                              pendingCommand.amountPaise !== undefined &&
                              pendingCommand.currentBalancePaise !== undefined &&
                              pendingCommand.amountPaise > pendingCommand.currentBalancePaise)) && styles.commandConfirmDisabled,
                          ]}
                          onPress={handleConfirmCommand}
                          disabled={loading || (pendingCommand.intent === 'repayment' &&
                            pendingCommand.amountPaise !== undefined &&
                            pendingCommand.currentBalancePaise !== undefined &&
                            pendingCommand.amountPaise > pendingCommand.currentBalancePaise)}
                        >
                          <Text style={styles.commandConfirmText}>
                            {pendingCommand.intent === 'stockout'
                              ? 'Confirm observation'
                              : pendingCommand.intent === 'stock_count'
                                ? 'Confirm physical count'
                                : pendingCommand.intent === 'customer_create'
                                  ? 'Confirm and add customer'
                                  : 'Confirm and record'}
                          </Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </>
                )}
              </View>
            )}

            {/* ── End-to-End "Aaj Kaisa Raha?" Brief Card ──────────────── */}
            {insightsBrief && (
              <View style={styles.briefCard}>
                <View style={styles.briefHeader}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Ionicons name="bar-chart" size={18} color="#0f3460" style={{ marginRight: 6 }} />
                    <Text style={styles.briefTitle}>Business Brief · Kirana Persona</Text>
                  </View>
                  <TouchableOpacity onPress={() => { setInsightsBrief(null); setAiExplanation(null); }}>
                    <Ionicons name="close-circle-outline" size={20} color="#6c757d" />
                  </TouchableOpacity>
                </View>

                {/* Synthetic Warning inside brief */}
                <View style={styles.briefSyntheticBanner}>
                  <Text style={styles.briefSyntheticText}>
                    ⚠ SYNTHETIC DATA — Derived from deterministic test fixture. Not Paytm data.
                  </Text>
                </View>

                {/* ── AI Explanation Card ──────────────────────────────── */}
                {aiExplanation && (
                  <View style={styles.aiExplanationCard}>
                    <View style={styles.aiExplanationHeader}>
                      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                        <Ionicons name="sparkles" size={14} color="#0f3460" style={{ marginRight: 4 }} />
                        <Text style={styles.aiExplanationTitle}>
                          {aiExplanation.fallback_used ? 'Summary (Deterministic)' : 'AI Summary (Facts-Only)'}
                        </Text>
                      </View>
                      {aiExplanation.fallback_used && (
                        <View style={styles.fallbackBadge}>
                          <Text style={styles.fallbackBadgeText}>FALLBACK</Text>
                        </View>
                      )}
                    </View>
                    <Text style={styles.aiExplanationText}>{aiExplanation.explanation}</Text>

                    {/* Evidence tags */}
                    {aiExplanation.evidence_ids.length > 0 && (
                      <View style={styles.evidenceRow}>
                        <Text style={styles.evidenceLabel}>Evidence:</Text>
                        {aiExplanation.evidence_ids.map((eid) => (
                          <View key={eid} style={styles.evidenceTag}>
                            <Text style={styles.evidenceTagText}>{eid}</Text>
                          </View>
                        ))}
                      </View>
                    )}

                    {/* Validation errors if any */}
                    {aiExplanation.validation_errors.length > 0 && (
                      <View style={styles.validationErrorBox}>
                        <Text style={styles.validationErrorTitle}>Fallback reason:</Text>
                        {aiExplanation.validation_errors.map((e, i) => (
                          <Text key={i} style={styles.validationErrorItem}>• {e}</Text>
                        ))}
                      </View>
                    )}
                  </View>
                )}

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

                {/* Proposed Merchant Action — from AI or fallback */}
                <View style={styles.mockActionCard}>
                  <View style={styles.mockActionHeader}>
                    <Text style={styles.mockActionTitle}>Proposed Merchant Action (Mock)</Text>
                    <View style={styles.mockBadge}>
                      <Text style={styles.mockBadgeText}>MOCK ONLY</Text>
                    </View>
                  </View>
                  <Text style={styles.mockActionDesc}>
                    Review or edit this shop-side notice. Approval saves a mock 7-day tracking record only; it is never published or sent.
                  </Text>
                  {aiExplanation?.action_type && (
                    <View style={styles.actionTypeBadge}>
                      <Text style={styles.actionTypeBadgeText}>
                        Action type: {aiExplanation.action_type}
                      </Text>
                    </View>
                  )}

                  <Text style={styles.actionDraftLabel}>Counter notice / action text</Text>
                  <TextInput
                    style={styles.actionDraftInput}
                    value={mockAction ? mockAction.action_text : mockActionDraft}
                    onChangeText={setMockActionDraft}
                    editable={!mockAction && !loading}
                    multiline
                    maxLength={240}
                    placeholder="Example: Ask us about this week's in-store offers."
                    accessibilityLabel="Editable mock merchant action text"
                  />
                  {!mockAction && (
                    <Text style={styles.actionDraftCount}>{mockActionDraft.length}/240 characters</Text>
                  )}

                  {mockAction ? (
                    <View style={styles.approvedBanner}>
                      <Ionicons name="checkmark-done-circle" size={18} color="#155724" style={{ marginRight: 6 }} />
                      <Text style={styles.approvedBannerText}>
                        Saved as merchant-approved (mock only). Nothing was published or sent.
                      </Text>
                    </View>
                  ) : (
                    <TouchableOpacity
                      style={[styles.approveBtn, (loading || !mockActionDraft.trim()) && { opacity: 0.6 }]}
                      onPress={handleApproveMockAction}
                      disabled={loading || !mockActionDraft.trim()}
                    >
                      {loading ? <ActivityIndicator size="small" color="#ffffff" style={{ marginRight: 6 }} /> :
                        <Ionicons name="hand-right-outline" size={16} color="#ffffff" style={{ marginRight: 6 }} />}
                      <Text style={styles.approveBtnText}>Approve & Track for 7 Days (Mock)</Text>
                    </TouchableOpacity>
                  )}
                  {mockAction && (
                    <View style={styles.outcomeCard}>
                      <Text style={styles.outcomeTitle}>Outcome check · {mockAction.outcome_status === 'scheduled' ? 'Scheduled' : mockAction.outcome_status === 'available' ? 'Observed' : 'No data'}</Text>
                      <Text style={styles.outcomeText}>{mockAction.outcome_note}</Text>
                      <Text style={styles.outcomeMeta}>
                        Baseline: {formatPeriodDate(mockAction.baseline_start, insightsBrief.period.timezone)}–{formatPeriodDate(mockAction.baseline_end, insightsBrief.period.timezone, true)} · {formatRupees(mockAction.baseline_collections_paise)} / {mockAction.baseline_transaction_count} payments
                      </Text>
                      <Text style={styles.outcomeMeta}>
                        Check window: {new Date(mockAction.measurement_start).toLocaleDateString('en-IN')}–{new Date(mockAction.measurement_end).toLocaleDateString('en-IN')}
                      </Text>
                      {mockAction.outcome_status === 'available' && mockAction.outcome_collections_paise !== null && (
                        <Text style={styles.outcomeMeta}>
                          Observed: {formatRupees(mockAction.outcome_collections_paise)} / {mockAction.outcome_transaction_count ?? 0} payments · change vs baseline {formatRupees(mockAction.collections_change_paise ?? 0)}
                        </Text>
                      )}
                      <Text style={styles.outcomeDisclaimer}>UPI only · a difference does not prove the action caused it · mock action was not published</Text>
                    </View>
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
                  <Text style={[styles.quickActionText, { color: '#28a745' }]}>-₹300 Jamma</Text>
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
            {!!voiceNotice && <Text style={styles.voiceNotice}>{voiceNotice}</Text>}
            <View style={styles.inputRow}>
              <TouchableOpacity
                style={[styles.micBtn, recorderState.isRecording && styles.micBtnActive]}
                onPress={recorderState.isRecording ? stopVoiceRecording : startVoiceRecording}
                disabled={loading || voiceBusy}
                accessibilityLabel={recorderState.isRecording ? 'Stop voice recording' : 'Start voice recording'}
              >
                {voiceBusy ? <ActivityIndicator size="small" color="#0f3460" /> :
                  <Ionicons name={recorderState.isRecording ? 'stop' : 'mic-outline'} size={19} color={recorderState.isRecording ? '#ffffff' : '#0f3460'} />}
              </TouchableOpacity>
              <TextInput
              style={styles.textInput}
              value={input}
              onChangeText={(value) => { setInput(value); setInputSourceChannel('text'); }}
              editable={!loading && !voiceBusy}
              placeholder="Try udhaar, jama, balance, or 'Aaj kaisa raha?'"
              placeholderTextColor="#9aa0a6"
              returnKeyType="send"
              onSubmitEditing={handleSubmitText}
            />
            <TouchableOpacity
              style={[styles.sendBtn, !input.trim() && styles.sendBtnDisabled]}
              onPress={handleSubmitText}
              disabled={!input.trim() || loading || voiceBusy}
            >
              <Ionicons name="send" size={18} color="#ffffff" />
            </TouchableOpacity>
            </View>
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

  // ── AI Explanation Card
  aiExplanationCard: {
    backgroundColor: '#e8f4fd',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#b6d4fe',
  },
  aiExplanationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  aiExplanationTitle: { fontSize: 13, fontWeight: '700', color: '#0f3460' },
  aiExplanationText: { fontSize: 13, color: '#212529', lineHeight: 19, marginBottom: 8 },
  fallbackBadge: {
    backgroundColor: '#e2e3e5',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  fallbackBadgeText: { fontSize: 9, fontWeight: '700', color: '#383d41' },
  evidenceRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  evidenceLabel: { fontSize: 10, fontWeight: '700', color: '#495057' },
  evidenceTag: {
    backgroundColor: '#cfe2ff',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  evidenceTagText: { fontSize: 9, fontWeight: '600', color: '#084298' },
  validationErrorBox: {
    backgroundColor: '#fff3cd',
    padding: 6,
    borderRadius: 4,
    marginTop: 4,
  },
  validationErrorTitle: { fontSize: 10, fontWeight: '700', color: '#856404' },
  validationErrorItem: { fontSize: 10, color: '#856404' },

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
  actionDraftLabel: { fontSize: 11, fontWeight: '700', color: '#495057', marginBottom: 4 },
  actionDraftInput: {
    minHeight: 64,
    borderWidth: 1,
    borderColor: '#adb5bd',
    borderRadius: 6,
    padding: 9,
    backgroundColor: '#ffffff',
    color: '#212529',
    fontSize: 12,
    lineHeight: 17,
    textAlignVertical: 'top',
  },
  actionDraftCount: { fontSize: 10, color: '#6c757d', textAlign: 'right', marginTop: 3, marginBottom: 6 },
  actionTypeBadge: {
    backgroundColor: '#d1ecf1',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginBottom: 8,
  },
  actionTypeBadgeText: { fontSize: 10, fontWeight: '600', color: '#0c5460' },
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
  outcomeCard: {
    marginTop: 10,
    padding: 10,
    borderRadius: 6,
    backgroundColor: '#f1f6f8',
    borderWidth: 1,
    borderColor: '#c8dce3',
  },
  outcomeTitle: { fontSize: 12, fontWeight: '800', color: '#0f3460', marginBottom: 4 },
  outcomeText: { fontSize: 11, color: '#34495e', lineHeight: 16, marginBottom: 5 },
  outcomeMeta: { fontSize: 10, color: '#495057', marginTop: 3 },
  outcomeDisclaimer: { fontSize: 10, color: '#856404', fontWeight: '600', marginTop: 6 },

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
  commandFeedback: {
    borderRadius: 8,
    borderWidth: 1,
    padding: 12,
    marginBottom: 10,
  },
  commandFeedback_info: { backgroundColor: '#e8f0fe', borderColor: '#b6ccf2' },
  commandFeedback_success: { backgroundColor: '#eef9f0', borderColor: '#b8dfbf' },
  commandFeedback_error: { backgroundColor: '#fff1f0', borderColor: '#f3b9b4' },
  commandFeedbackTitle: { fontSize: 13, fontWeight: '700', color: '#17324d', marginBottom: 3 },
  commandFeedbackText: { fontSize: 12, color: '#3c4856', lineHeight: 18 },
  commandPreviewCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#0f3460',
    padding: 14,
    marginBottom: 12,
    elevation: 2,
  },
  commandPreviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  commandPreviewTitle: { fontSize: 15, fontWeight: '800', color: '#0f3460' },
  commandNotSavedBadge: {
    backgroundColor: '#fff3cd',
    borderRadius: 4,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  commandNotSavedText: { color: '#856404', fontSize: 9, fontWeight: '800' },
  commandPreviewText: { color: '#343a40', fontSize: 13, lineHeight: 19, marginBottom: 4 },
  commandPreviewAmount: { color: '#0f3460', fontSize: 18, fontWeight: '800', marginVertical: 5 },
  commandPreviewNote: { color: '#856404', fontSize: 11, lineHeight: 16, marginTop: 5 },
  commandBlockedText: { color: '#a61b1b', fontSize: 12, fontWeight: '600', marginTop: 5 },
  commandMatchButton: {
    backgroundColor: '#f8f9fa',
    borderWidth: 1,
    borderColor: '#d7dde5',
    borderRadius: 6,
    padding: 10,
    marginTop: 7,
  },
  commandMatchName: { color: '#0f3460', fontSize: 13, fontWeight: '700' },
  commandMatchId: { color: '#6c757d', fontSize: 10, marginTop: 2 },
  commandButtonRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  commandCancelButton: {
    backgroundColor: '#f1f3f5',
    borderRadius: 6,
    paddingVertical: 10,
    alignItems: 'center',
    flex: 1,
  },
  commandCancelText: { color: '#495057', fontSize: 12, fontWeight: '700' },
  commandConfirmButton: {
    backgroundColor: '#0f3460',
    borderRadius: 6,
    paddingVertical: 10,
    alignItems: 'center',
    flex: 2,
  },
  commandConfirmDisabled: { backgroundColor: '#adb5bd' },
  commandConfirmText: { color: '#ffffff', fontSize: 12, fontWeight: '700' },
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
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#dee2e6',
    backgroundColor: '#ffffff',
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  voiceNotice: {
    fontSize: 10,
    color: '#495057',
    lineHeight: 14,
    marginBottom: 5,
    paddingHorizontal: 3,
  },
  micBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#e8f0fe',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  micBtnActive: {
    backgroundColor: '#dc3545',
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
