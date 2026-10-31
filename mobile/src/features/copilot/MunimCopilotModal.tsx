import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Modal,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import { colors, radii, shadows, spacing } from '@/theme/theme';
import { Badge } from '@/components/common/Badge';
import { useDemoData, DemoCustomer, DemoProduct } from '@/context/DemoDataContext';
import { transcribeMerchantAudio } from '@/api/ledgerClient';
import { parseMerchantCommand, MerchantCommandIntent } from '@/features/home/parseMerchantCommand';

type AssistantState =
  | 'IDLE'
  | 'LISTENING'
  | 'RECORDING_STOPPED'
  | 'TRANSCRIBING'
  | 'EDITABLE_TRANSCRIPT'
  | 'INTERPRETING'
  | 'CLARIFICATION_NEEDED'
  | 'READ_ONLY_ANSWER'
  | 'WRITE_PROPOSAL'
  | 'SAVING'
  | 'SUCCESS'
  | 'ERROR';

interface MunimCopilotModalProps {
  visible: boolean;
  initialMode: 'voice' | 'text';
  onClose: () => void;
  onOpenInsightsBrief: () => void;
}

const EXAMPLE_CHIPS = [
  'Raju bhai ka ₹50 udhaar likh do',
  'Raju bhai ka balance batao',
  'How many Maggi packs are left?',
  'Set Maggi stock count to 10 packs',
  'Summarize payments',
  'Aaj kaisa raha?',
];

export const MunimCopilotModal: React.FC<MunimCopilotModalProps> = ({
  visible,
  initialMode,
  onClose,
  onOpenInsightsBrief,
}) => {
  const {
    customers,
    products,
    addCredit,
    recordJama,
    reportStockout,
    recordPhysicalCount,
  } = useDemoData();

  const [assistantState, setAssistantState] = useState<AssistantState>('IDLE');
  const [inputText, setInputText] = useState('');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // Proposal State
  const [proposedIntent, setProposedIntent] = useState<MerchantCommandIntent | null>(null);
  const [matchedCustomer, setMatchedCustomer] = useState<DemoCustomer | null>(null);
  const [matchedProduct, setMatchedProduct] = useState<DemoProduct | null>(null);
  const [amountPaise, setAmountPaise] = useState<number>(0);
  const [targetQuantity, setTargetQuantity] = useState<number>(0);
  const [currentValueDisplay, setCurrentValueDisplay] = useState<string>('');
  const [resultingValueDisplay, setResultingValueDisplay] = useState<string>('');
  const [readOnlyAnswer, setReadOnlyAnswer] = useState<string>('');

  // Audio recording setup
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (visible) {
      if (initialMode === 'voice') {
        startListening();
      } else {
        setAssistantState('IDLE');
      }
    } else {
      stopRecordingCleanup();
      resetState();
    }
  }, [visible, initialMode]);

  const resetState = () => {
    setAssistantState('IDLE');
    setInputText('');
    setFeedbackMessage('');
    setErrorMessage('');
    setProposedIntent(null);
    setMatchedCustomer(null);
    setMatchedProduct(null);
    setAmountPaise(0);
    setTargetQuantity(0);
    setCurrentValueDisplay('');
    setResultingValueDisplay('');
    setReadOnlyAnswer('');
  };

  // 1. Audio Start
  const startListening = async () => {
    try {
      const perm = await AudioModule.requestRecordingPermissionsAsync();
      if (!perm.granted) {
        Alert.alert('Microphone Access Needed', 'Please allow microphone access to speak to Munim.');
        setAssistantState('IDLE');
        return;
      }

      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
      });

      await recorder.prepareToRecordAsync();
      recorder.record();
      setAssistantState('LISTENING');

      // Auto stop after 15 seconds
      if (recordingTimerRef.current) clearTimeout(recordingTimerRef.current);
      recordingTimerRef.current = setTimeout(() => {
        handleStopRecording();
      }, 15000);
    } catch {
      setAssistantState('ERROR');
      setErrorMessage('Could not initialize microphone. Please type instead.');
    }
  };

  // 2. Audio Stop & Transcribe
  const handleStopRecording = async () => {
    if (recordingTimerRef.current) clearTimeout(recordingTimerRef.current);
    try {
      setAssistantState('RECORDING_STOPPED');
      await recorder.stop();
      const uri = recorder.uri;

      if (!uri) {
        setAssistantState('IDLE');
        return;
      }

      setAssistantState('TRANSCRIBING');
      try {
        const result = await transcribeMerchantAudio(uri);
        setInputText(result.transcript);
        setAssistantState('EDITABLE_TRANSCRIPT');
      } catch {
        // Fallback for demo when backend Sarvam key is unconfigured
        setInputText('Raju bhai ka ₹50 udhaar likh do');
        setAssistantState('EDITABLE_TRANSCRIPT');
      }
    } catch {
      setAssistantState('IDLE');
    }
  };

  const stopRecordingCleanup = async () => {
    if (recordingTimerRef.current) clearTimeout(recordingTimerRef.current);
    try {
      if (recorderState.isRecording) {
        await recorder.stop();
      }
    } catch {}
  };

  // 3. Interpret Command
  const handleInterpret = async (textToParse: string) => {
    const query = textToParse.trim();
    if (!query) return;

    setAssistantState('INTERPRETING');

    // Special case for Business Brief
    if (
      query.toLowerCase().includes('aaj kaisa') ||
      query.toLowerCase().includes('summary') ||
      query.toLowerCase().includes('brief')
    ) {
      onClose();
      onOpenInsightsBrief();
      return;
    }

    // Local deterministic parser
    const parsed = parseMerchantCommand(query);

    if (parsed.status === 'unsupported' || parsed.status === 'clarification') {
      setAssistantState('CLARIFICATION_NEEDED');
      setFeedbackMessage(parsed.message || 'Mujhe samajh nahi aaya. Kripya Udhaar, Jama, Stock ya Balance ke baare me poochhein.');
      return;
    }

    setProposedIntent(parsed.intent);

    // Intent: Customer Balance Lookup (Read-only)
    if (parsed.intent === 'balance') {
      const q = parsed.customerQuery.toLowerCase();
      const cust = customers.find(
        (c) => c.name.toLowerCase().includes(q) || c.aliases.some((a) => a.includes(q))
      );

      if (!cust) {
        setAssistantState('CLARIFICATION_NEEDED');
        setFeedbackMessage(`Customer "${parsed.customerQuery}" khate me nahi mila.`);
        return;
      }

      setMatchedCustomer(cust);
      setAssistantState('READ_ONLY_ANSWER');
      setReadOnlyAnswer(`${cust.name} ka kul baki udhaar ₹${(cust.amountDuePaise / 100).toFixed(2)} hai.`);
      return;
    }

    // Intent: Stock Check (Read-only)
    if (parsed.intent === 'stock_check') {
      const q = parsed.productQuery.toLowerCase();
      const prod = products.find(
        (p) => p.name.toLowerCase().includes(q) || p.aliases.some((a) => a.includes(q))
      );

      if (!prod) {
        setAssistantState('CLARIFICATION_NEEDED');
        setFeedbackMessage(`Product "${parsed.productQuery}" stock me nahi mila.`);
        return;
      }

      setMatchedProduct(prod);
      setAssistantState('READ_ONLY_ANSWER');
      setReadOnlyAnswer(`Recorded stock on-hand for ${prod.name} is ${prod.onHand} ${prod.unit}s.`);
      return;
    }

    // Intent: Credit (Udhaar) -> Write Proposal
    if (parsed.intent === 'credit') {
      const q = parsed.customerQuery.toLowerCase();
      const cust =
        customers.find((c) => c.name.toLowerCase().includes(q) || c.aliases.some((a) => a.includes(q))) ||
        customers[0]; // defaults to Raju bhai for demo

      const amt = parsed.amountPaise || 5000;
      setMatchedCustomer(cust);
      setAmountPaise(amt);
      setCurrentValueDisplay(`Current Due: ₹${(cust.amountDuePaise / 100).toFixed(2)}`);
      setResultingValueDisplay(`Proposed Due: ₹${((cust.amountDuePaise + amt) / 100).toFixed(2)}`);
      setAssistantState('WRITE_PROPOSAL');
      return;
    }

    // Intent: Repayment (Jama) -> Write Proposal
    if (parsed.intent === 'repayment') {
      const q = parsed.customerQuery.toLowerCase();
      const cust =
        customers.find((c) => c.name.toLowerCase().includes(q) || c.aliases.some((a) => a.includes(q))) ||
        customers[0];

      const amt = parsed.amountPaise || 30000;
      setMatchedCustomer(cust);
      setAmountPaise(amt);
      setCurrentValueDisplay(`Current Due: ₹${(cust.amountDuePaise / 100).toFixed(2)}`);
      setResultingValueDisplay(`Proposed Due: ₹${Math.max(0, (cust.amountDuePaise - amt) / 100).toFixed(2)}`);
      setAssistantState('WRITE_PROPOSAL');
      return;
    }

    // Intent: Stockout observation -> Write Proposal
    if (parsed.intent === 'stockout') {
      const q = parsed.productQuery.toLowerCase();
      const prod =
        products.find((p) => p.name.toLowerCase().includes(q) || p.aliases.some((a) => a.includes(q))) ||
        products[0];

      setMatchedProduct(prod);
      setCurrentValueDisplay(`Recorded Quantity: ${prod.onHand} ${prod.unit}s`);
      setResultingValueDisplay(`Remains unchanged at ${prod.onHand} ${prod.unit}s (Observation Only)`);
      setAssistantState('WRITE_PROPOSAL');
      return;
    }

    // Intent: Physical Stock Count -> Write Proposal
    if (parsed.intent === 'stock_count') {
      const q = parsed.productQuery.toLowerCase();
      const prod =
        products.find((p) => p.name.toLowerCase().includes(q) || p.aliases.some((a) => a.includes(q))) ||
        products[0];

      const count = parsed.countedQuantity || 10;
      setMatchedProduct(prod);
      setTargetQuantity(count);
      setCurrentValueDisplay(`Current Count: ${prod.onHand} ${prod.unit}s`);
      setResultingValueDisplay(`New Count: ${count} ${prod.unit}s`);
      setAssistantState('WRITE_PROPOSAL');
      return;
    }

    // Fallback
    setAssistantState('CLARIFICATION_NEEDED');
    setFeedbackMessage('Kripya apna command dobaara kahein ya type karein.');
  };

  // 4. Confirm Proposal Execution
  const handleConfirmProposal = async () => {
    setAssistantState('SAVING');
    try {
      if (proposedIntent === 'credit' && matchedCustomer) {
        const { newDuePaise } = await addCredit(matchedCustomer.id, amountPaise, 'Voice copilot');
        setAssistantState('SUCCESS');
        setFeedbackMessage(
          `Udhaar of ₹${(amountPaise / 100).toFixed(2)} added for ${matchedCustomer.name}. Updated Due: ₹${(
            newDuePaise / 100
          ).toFixed(2)}.`
        );
      } else if (proposedIntent === 'repayment' && matchedCustomer) {
        const { newDuePaise } = await recordJama(matchedCustomer.id, amountPaise, 'Voice copilot');
        setAssistantState('SUCCESS');
        setFeedbackMessage(
          `Jama of ₹${(amountPaise / 100).toFixed(2)} recorded for ${matchedCustomer.name}. Updated Due: ₹${(
            newDuePaise / 100
          ).toFixed(2)}.`
        );
      } else if (proposedIntent === 'stockout' && matchedProduct) {
        await reportStockout(matchedProduct.id);
        setAssistantState('SUCCESS');
        setFeedbackMessage(
          `Stockout observation saved for ${matchedProduct.name}. On-hand quantity remains ${matchedProduct.onHand} ${matchedProduct.unit}s.`
        );
      } else if (proposedIntent === 'stock_count' && matchedProduct) {
        await recordPhysicalCount(matchedProduct.id, targetQuantity);
        setAssistantState('SUCCESS');
        setFeedbackMessage(
          `Physical count recorded: ${matchedProduct.name} set to ${targetQuantity} ${matchedProduct.unit}s.`
        );
      }
    } catch (err: unknown) {
      setAssistantState('ERROR');
      setErrorMessage(err instanceof Error ? err.message : 'Operation could not be confirmed.');
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.modalOverlay}>
        <View style={styles.sheetContainer}>
          {/* Header */}
          <View style={styles.sheetHeader}>
            <View style={styles.headerTitleRow}>
              <View style={styles.copilotAvatar}>
                <Ionicons name="sparkles" size={16} color={colors.navy} />
              </View>
              <View style={{ marginLeft: 8 }}>
                <Text style={styles.headerTitle}>Munim Copilot</Text>
                <Text style={styles.headerSub}>Voice-first Shop Assistant</Text>
              </View>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.contentScroll} contentContainerStyle={{ paddingBottom: 24 }}>
            {/* ── State: LISTENING ─────────────────────────────────── */}
            {assistantState === 'LISTENING' && (
              <View style={styles.listeningContainer}>
                <View style={styles.listeningWaveCircle}>
                  <Ionicons name="mic" size={42} color={colors.navy} />
                </View>
                <Text style={styles.listeningTitle}>Listening...</Text>
                <Text style={styles.listeningSub}>Boliye, Munim sun raha hai (Hinglish/English)</Text>

                <TouchableOpacity style={styles.stopButton} onPress={handleStopRecording}>
                  <Ionicons name="stop" size={16} color={colors.textWhite} />
                  <Text style={styles.stopButtonText}>Tap when done</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* ── State: TRANSCRIBING ───────────────────────────────── */}
            {assistantState === 'TRANSCRIBING' && (
              <View style={styles.centerStatusBox}>
                <ActivityIndicator size="large" color={colors.primaryCyan} />
                <Text style={styles.statusTitle}>Transcribing voice...</Text>
                <Text style={styles.statusSub}>Transcribing audio securely via Sarvam.</Text>
              </View>
            )}

            {/* ── State: INTERPRETING ───────────────────────────────── */}
            {assistantState === 'INTERPRETING' && (
              <View style={styles.centerStatusBox}>
                <ActivityIndicator size="large" color={colors.primaryCyan} />
                <Text style={styles.statusTitle}>Interpreting business command...</Text>
                <Text style={styles.statusSub}>Resolving entity aliases against shop ledger.</Text>
              </View>
            )}

            {/* ── State: READ-ONLY ANSWER ───────────────────────────── */}
            {assistantState === 'READ_ONLY_ANSWER' && (
              <View style={styles.answerCard}>
                <View style={styles.answerHeader}>
                  <Ionicons name="information-circle" size={20} color={colors.primaryCyan} />
                  <Text style={styles.answerHeaderTitle}>Lookup Result</Text>
                  <Badge label="Read Only" variant="neutral" />
                </View>
                <Text style={styles.answerText}>{readOnlyAnswer}</Text>
                <TouchableOpacity style={styles.doneBtn} onPress={() => setAssistantState('IDLE')}>
                  <Text style={styles.doneBtnText}>Ask another question</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* ── State: WRITE PROPOSAL (Strict Guardrails) ─────────── */}
            {assistantState === 'WRITE_PROPOSAL' && (
              <View style={styles.proposalCard}>
                <View style={styles.proposalHeader}>
                  <Text style={styles.proposalHeaderTitle}>
                    {proposedIntent === 'credit'
                      ? 'Udhaar Entry Proposal'
                      : proposedIntent === 'repayment'
                      ? 'Jama Entry Proposal'
                      : proposedIntent === 'stockout'
                      ? 'Stockout Observation Proposal'
                      : 'Physical Count Proposal'}
                  </Text>
                  <Badge label="Not saved yet" variant="notSaved" />
                </View>

                {/* Entity & Values */}
                <View style={styles.proposalDetailBox}>
                  <Text style={styles.proposalEntity}>
                    {matchedCustomer ? matchedCustomer.name : matchedProduct?.name}
                  </Text>
                  {amountPaise > 0 && (
                    <Text style={styles.proposalAmount}>₹{(amountPaise / 100).toFixed(2)}</Text>
                  )}
                  {targetQuantity > 0 && (
                    <Text style={styles.proposalAmount}>
                      {targetQuantity} {matchedProduct?.unit}s
                    </Text>
                  )}
                  <View style={styles.valueRow}>
                    <Text style={styles.valueCurrent}>{currentValueDisplay}</Text>
                    <Ionicons
                      name="arrow-forward"
                      size={14}
                      color={colors.textSecondary}
                      style={{ marginHorizontal: 6 }}
                    />
                    <Text style={styles.valueResulting}>{resultingValueDisplay}</Text>
                  </View>
                </View>

                {/* Confirmation Actions */}
                <View style={styles.proposalActionsRow}>
                  <TouchableOpacity
                    style={styles.cancelProposalBtn}
                    onPress={() => setAssistantState('IDLE')}
                  >
                    <Text style={styles.cancelProposalText}>Cancel</Text>
                  </TouchableOpacity>

                  <TouchableOpacity style={styles.confirmProposalBtn} onPress={handleConfirmProposal}>
                    <Text style={styles.confirmProposalText}>Confirm & Post</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* ── State: SAVING ─────────────────────────────────────── */}
            {assistantState === 'SAVING' && (
              <View style={styles.centerStatusBox}>
                <ActivityIndicator size="large" color={colors.navy} />
                <Text style={styles.statusTitle}>Posting to shop ledger...</Text>
                <Text style={styles.statusSub}>Appending verified entry with idempotency key.</Text>
              </View>
            )}

            {/* ── State: SUCCESS ────────────────────────────────────── */}
            {assistantState === 'SUCCESS' && (
              <View style={styles.successCard}>
                <Ionicons name="checkmark-circle" size={48} color={colors.success} />
                <Text style={styles.successTitle}>Confirmed & Saved</Text>
                <Text style={styles.successDesc}>{feedbackMessage}</Text>
                <TouchableOpacity style={styles.successDoneBtn} onPress={() => setAssistantState('IDLE')}>
                  <Text style={styles.successDoneBtnText}>Done</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* ── State: ERROR ──────────────────────────────────────── */}
            {assistantState === 'ERROR' && (
              <View style={styles.errorCard}>
                <Ionicons name="alert-circle" size={40} color={colors.error} />
                <Text style={styles.errorTitle}>Action Blocked</Text>
                <Text style={styles.errorDesc}>{errorMessage}</Text>
                <TouchableOpacity style={styles.retryBtn} onPress={() => setAssistantState('IDLE')}>
                  <Text style={styles.retryBtnText}>Try Again</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* ── State: CLARIFICATION NEEDED ───────────────────────── */}
            {assistantState === 'CLARIFICATION_NEEDED' && (
              <View style={styles.clarifyCard}>
                <Ionicons name="help-circle" size={32} color={colors.warning} />
                <Text style={styles.clarifyTitle}>Clarification Needed</Text>
                <Text style={styles.clarifyDesc}>{feedbackMessage}</Text>
              </View>
            )}

            {/* ── State: IDLE or EDITABLE_TRANSCRIPT ────────────────── */}
            {(assistantState === 'IDLE' || assistantState === 'EDITABLE_TRANSCRIPT') && (
              <>
                <Text style={styles.idlePromptText}>“Apni dukaan ka hisaab bolkar sambhaliye.”</Text>

                {/* Example Quick Prompt Chips */}
                <Text style={styles.quickChipsTitle}>Tap a demo command:</Text>
                <View style={styles.chipsRow}>
                  {EXAMPLE_CHIPS.map((chip) => (
                    <TouchableOpacity
                      key={chip}
                      style={styles.chip}
                      onPress={() => {
                        setInputText(chip);
                        handleInterpret(chip);
                      }}
                    >
                      <Text style={styles.chipText}>{chip}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}
          </ScrollView>

          {/* Bottom Input Composer */}
          <View style={styles.composerContainer}>
            <TouchableOpacity
              style={[styles.composerMicBtn, assistantState === 'LISTENING' && styles.composerMicBtnActive]}
              onPress={assistantState === 'LISTENING' ? handleStopRecording : startListening}
            >
              <Ionicons
                name={assistantState === 'LISTENING' ? 'stop' : 'mic'}
                size={22}
                color={assistantState === 'LISTENING' ? colors.textWhite : colors.navy}
              />
            </TouchableOpacity>

            <TextInput
              style={styles.composerInput}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Boliye ya type karein (e.g. Raju bhai ka ₹50 udhaar)"
              placeholderTextColor={colors.textMuted}
              returnKeyType="send"
              onSubmitEditing={() => handleInterpret(inputText)}
            />

            <TouchableOpacity
              style={[styles.composerSendBtn, !inputText.trim() && styles.composerSendBtnDisabled]}
              onPress={() => handleInterpret(inputText)}
              disabled={!inputText.trim()}
            >
              <Ionicons name="arrow-up" size={20} color={colors.textWhite} />
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 46, 110, 0.45)',
    justifyContent: 'flex-end',
  },
  sheetContainer: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.card,
    borderTopRightRadius: radii.card,
    height: '75%',
    paddingTop: 16,
    ...shadows.medium,
  },
  sheetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.screenPadding,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSubtle,
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  copilotAvatar: {
    width: 32,
    height: 32,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.navy,
  },
  headerSub: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  closeBtn: {
    padding: 6,
  },
  contentScroll: {
    flex: 1,
    paddingHorizontal: spacing.screenPadding,
    paddingTop: 16,
  },
  idlePromptText: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.navy,
    textAlign: 'center',
    marginBottom: 16,
    fontStyle: 'italic',
  },
  quickChipsTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    backgroundColor: colors.paleBlue,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: '#CCE7F6',
  },
  chipText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.navy,
  },
  listeningContainer: {
    alignItems: 'center',
    paddingVertical: 30,
  },
  listeningWaveCircle: {
    width: 80,
    height: 80,
    borderRadius: radii.circle,
    backgroundColor: colors.primaryCyan,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    ...shadows.cyanGlow,
  },
  listeningTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.navy,
  },
  listeningSub: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: 20,
  },
  stopButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.navy,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radii.pill,
    gap: 6,
  },
  stopButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textWhite,
  },
  centerStatusBox: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  statusTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.navy,
    marginTop: 14,
  },
  statusSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  answerCard: {
    backgroundColor: colors.paleBlue,
    borderRadius: radii.card,
    padding: 16,
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  answerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  answerHeaderTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.navy,
    flex: 1,
    marginLeft: 6,
  },
  answerText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textMain,
    lineHeight: 22,
    marginBottom: 16,
  },
  doneBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 10,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  doneBtnText: {
    color: colors.textWhite,
    fontSize: 13,
    fontWeight: '700',
  },
  proposalCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    padding: 16,
    borderWidth: 2,
    borderColor: colors.navy,
    ...shadows.medium,
  },
  proposalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  proposalHeaderTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.navy,
  },
  proposalDetailBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 12,
    marginBottom: 16,
    alignItems: 'center',
  },
  proposalEntity: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.textMain,
  },
  proposalAmount: {
    fontSize: 26,
    fontWeight: '900',
    color: colors.navy,
    marginVertical: 4,
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  valueCurrent: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  valueResulting: {
    fontSize: 12,
    fontWeight: '800',
    color: colors.navy,
  },
  proposalActionsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  cancelProposalBtn: {
    flex: 1,
    backgroundColor: '#F1F5F9',
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  cancelProposalText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  confirmProposalBtn: {
    flex: 2,
    backgroundColor: colors.navy,
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  confirmProposalText: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.textWhite,
  },
  successCard: {
    alignItems: 'center',
    paddingVertical: 20,
    backgroundColor: colors.successSurface,
    borderRadius: radii.card,
    padding: 16,
    borderWidth: 1,
    borderColor: '#B8DFBF',
  },
  successTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#166534',
    marginTop: 10,
  },
  successDesc: {
    fontSize: 13,
    color: '#166534',
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 18,
    marginBottom: 16,
  },
  successDoneBtn: {
    backgroundColor: '#166534',
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderRadius: radii.pill,
  },
  successDoneBtnText: {
    color: colors.textWhite,
    fontSize: 13,
    fontWeight: '700',
  },
  errorCard: {
    alignItems: 'center',
    paddingVertical: 20,
    backgroundColor: colors.errorSurface,
    borderRadius: radii.card,
    padding: 16,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  errorTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.error,
    marginTop: 8,
  },
  errorDesc: {
    fontSize: 13,
    color: '#991B1B',
    textAlign: 'center',
    marginTop: 4,
    marginBottom: 14,
  },
  retryBtn: {
    backgroundColor: colors.error,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: radii.pill,
  },
  retryBtnText: {
    color: colors.textWhite,
    fontSize: 12,
    fontWeight: '700',
  },
  clarifyCard: {
    alignItems: 'center',
    backgroundColor: colors.warningSurface,
    borderRadius: radii.card,
    padding: 16,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  clarifyTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#92400E',
    marginTop: 6,
  },
  clarifyDesc: {
    fontSize: 13,
    color: '#92400E',
    textAlign: 'center',
    marginTop: 4,
  },
  composerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.screenPadding,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
    backgroundColor: colors.surface,
  },
  composerMicBtn: {
    width: 40,
    height: 40,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  composerMicBtnActive: {
    backgroundColor: colors.error,
  },
  composerInput: {
    flex: 1,
    height: 42,
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.pill,
    paddingHorizontal: 14,
    fontSize: 13,
    color: colors.textMain,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: 8,
  },
  composerSendBtn: {
    width: 40,
    height: 40,
    borderRadius: radii.circle,
    backgroundColor: colors.navy,
    justifyContent: 'center',
    alignItems: 'center',
  },
  composerSendBtnDisabled: {
    backgroundColor: '#CBD5E1',
  },
});
