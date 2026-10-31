import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { Badge } from '@/components/common/Badge';
import { useDemoData } from '@/context/DemoDataContext';

interface ExtractedKhataRow {
  id: string;
  customerName: string;
  type: 'CREDIT' | 'REPAYMENT';
  amountPaise: number;
  note: string;
  confidence: number;
  status: 'READY' | 'NEEDS_REVIEW';
  issue?: string;
}

const INITIAL_EXTRACTED_ROWS: ExtractedKhataRow[] = [
  {
    id: 'row_1',
    customerName: 'Raju bhai',
    type: 'CREDIT',
    amountPaise: 5000, // ₹50
    note: 'Sugar + Atta',
    confidence: 0.94,
    status: 'READY',
  },
  {
    id: 'row_2',
    customerName: 'Sunita Devi',
    type: 'REPAYMENT',
    amountPaise: 12000, // ₹120
    note: 'Cash deposit',
    confidence: 0.91,
    status: 'READY',
  },
  {
    id: 'row_3',
    customerName: 'Mahesh (Ambiguous)',
    type: 'CREDIT',
    amountPaise: 2500, // ₹25
    note: 'Soap',
    confidence: 0.62,
    status: 'NEEDS_REVIEW',
    issue: '2 customers matched: Mahesh tailor vs Mahesh kirana',
  },
];

interface BahiKhataScanScreenProps {
  onBack?: () => void;
  onDone?: () => void;
}

export const BahiKhataScanScreen: React.FC<BahiKhataScanScreenProps> = ({ onBack, onDone }) => {
  const { addCredit, recordJama } = useDemoData();
  const [step, setStep] = useState<'CAPTURE' | 'EXTRACTING' | 'EDITABLE_ROWS' | 'POSTED'>('EDITABLE_ROWS');
  const [rows, setRows] = useState<ExtractedKhataRow[]>(INITIAL_EXTRACTED_ROWS);

  const handleSimulateExtract = () => {
    setStep('EXTRACTING');
    setTimeout(() => {
      setStep('EDITABLE_ROWS');
    }, 1500);
  };

  const handleConfirmValidRows = async () => {
    // Only post READY rows
    const readyRows = rows.filter((r) => r.status === 'READY');
    for (const r of readyRows) {
      if (r.type === 'CREDIT') {
        await addCredit('cust_raju_01', r.amountPaise, `Bahi-Khata scan: ${r.note}`);
      } else {
        await recordJama('cust_sunita_02', r.amountPaise, `Bahi-Khata scan: ${r.note}`);
      }
    }
    setStep('POSTED');
  };

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {onBack && step !== 'POSTED' && (
          <TouchableOpacity style={styles.backBtn} onPress={onBack}>
            <Ionicons name="arrow-back" size={20} color={colors.navy} />
            <Text style={styles.backBtnText}>Back</Text>
          </TouchableOpacity>
        )}

        {/* ── STEP: CAPTURE ─────────────────────────────────────────── */}
        {step === 'CAPTURE' && (
          <View style={styles.captureBox}>
            <View style={styles.notebookIconBox}>
              <Ionicons name="book-outline" size={56} color={colors.navy} />
              <Text style={styles.captureTitle}>Scan Handwritten Bahi-Khata</Text>
              <Text style={styles.captureSub}>
                Capture diary or notebook ledger entries into validated digital khata drafts.
              </Text>
            </View>

            <TouchableOpacity style={styles.takePhotoBtn} onPress={handleSimulateExtract}>
              <Ionicons name="camera" size={20} color={colors.textWhite} />
              <Text style={styles.takePhotoBtnText}>Capture Notebook Page (Demo)</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── STEP: EXTRACTING ──────────────────────────────────────── */}
        {step === 'EXTRACTING' && (
          <View style={styles.extractingCenter}>
            <ActivityIndicator size="large" color={colors.primaryCyan} />
            <Text style={styles.extractingTitle}>Reading Handwritten Entries...</Text>
            <Text style={styles.extractingSub}>
              Detecting names, credit/jama flags, and rupee amounts. Highlighting uncertain lines.
            </Text>
          </View>
        )}

        {/* ── STEP: EDITABLE ROWS ───────────────────────────────────── */}
        {step === 'EDITABLE_ROWS' && (
          <>
            <View style={styles.draftHeaderRow}>
              <View>
                <Text style={styles.draftTitle}>Bahi-Khata Scanned Draft</Text>
                <Text style={styles.draftSub}>
                  Draft only — customer balances have NOT been changed.
                </Text>
              </View>
              <Badge label="Draft — not posted" variant="draft" />
            </View>

            {/* Notebook Preview Warning */}
            <View style={styles.notebookWarningBox}>
              <Ionicons name="shield-checkmark-outline" size={18} color={colors.navy} />
              <Text style={styles.notebookWarningText}>
                No Guessing Policy: Unreadable words or ambiguous customer names are flagged for merchant choice.
              </Text>
            </View>

            {/* Extracted Rows */}
            {rows.map((row) => (
              <PaytmCard key={row.id} style={styles.rowCard}>
                <View style={styles.rowTop}>
                  <View style={styles.rowCustomerBlock}>
                    <Text style={styles.rowCustomerName}>{row.customerName}</Text>
                    <Text style={styles.rowNote}>{row.note}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text
                      style={[
                        styles.rowAmount,
                        { color: row.type === 'CREDIT' ? colors.udhaarRed : colors.jamaGreen },
                      ]}
                    >
                      {row.type === 'CREDIT' ? '+' : '-'} ₹{(row.amountPaise / 100).toFixed(2)}
                    </Text>
                    <Badge
                      label={row.status === 'READY' ? 'Verified' : 'Needs Choice'}
                      variant={row.status === 'READY' ? 'success' : 'warning'}
                    />
                  </View>
                </View>

                {row.issue && (
                  <View style={styles.rowIssueBox}>
                    <Ionicons name="alert-circle" size={14} color="#92400E" />
                    <Text style={styles.rowIssueText}>{row.issue}</Text>
                  </View>
                )}
              </PaytmCard>
            ))}

            <TouchableOpacity style={styles.postValidBtn} onPress={handleConfirmValidRows}>
              <Text style={styles.postValidBtnText}>Confirm & Post Verified Rows (2)</Text>
            </TouchableOpacity>
          </>
        )}

        {/* ── STEP: POSTED RESULT ────────────────────────────────────── */}
        {step === 'POSTED' && (
          <PaytmCard style={styles.postedCard}>
            <Ionicons name="checkmark-circle" size={54} color={colors.success} />
            <Text style={styles.postedTitle}>Bahi-Khata Rows Posted</Text>
            <Text style={styles.postedSub}>
              2 verified ledger entries successfully appended to Raju bhai and Sunita Devi's khata. Ambiguous lines remain in review queue.
            </Text>

            <TouchableOpacity style={styles.postedDoneBtn} onPress={onDone || onBack}>
              <Text style={styles.postedDoneBtnText}>Return to Khata</Text>
            </TouchableOpacity>
          </PaytmCard>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scroll: { flex: 1 },
  content: { padding: spacing.screenPadding, paddingBottom: 40 },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  backBtnText: { fontSize: 14, fontWeight: '700', color: colors.navy },
  captureBox: { alignItems: 'center', paddingVertical: 40 },
  notebookIconBox: {
    width: '100%',
    padding: 30,
    backgroundColor: colors.paleBlue,
    borderRadius: radii.card,
    borderWidth: 2,
    borderColor: '#BAE6FD',
    alignItems: 'center',
    marginBottom: 20,
  },
  captureTitle: { fontSize: 18, fontWeight: '800', color: colors.navy, marginTop: 12 },
  captureSub: { fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: 4 },
  takePhotoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    width: '100%',
    gap: 8,
  },
  takePhotoBtnText: { fontSize: 14, fontWeight: '800', color: colors.textWhite },
  extractingCenter: { alignItems: 'center', paddingVertical: 60 },
  extractingTitle: { fontSize: 16, fontWeight: '800', color: colors.navy, marginTop: 14 },
  extractingSub: { fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: 4 },
  draftHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  draftTitle: { fontSize: 17, fontWeight: '800', color: colors.navy },
  draftSub: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  notebookWarningBox: {
    flexDirection: 'row',
    backgroundColor: colors.paleBlue,
    borderRadius: radii.cardSmall,
    padding: 10,
    gap: 8,
    marginBottom: 12,
  },
  notebookWarningText: { fontSize: 11, color: colors.navy, flex: 1, lineHeight: 15 },
  rowCard: { marginBottom: 10, padding: 12 },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  rowCustomerBlock: { flex: 1 },
  rowCustomerName: { fontSize: 14, fontWeight: '800', color: colors.textMain },
  rowNote: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  rowAmount: { fontSize: 16, fontWeight: '900', marginBottom: 2 },
  rowIssueBox: {
    flexDirection: 'row',
    backgroundColor: colors.warningSurface,
    borderRadius: radii.cardSmall,
    padding: 8,
    marginTop: 8,
    gap: 6,
  },
  rowIssueText: { fontSize: 11, color: '#92400E', fontWeight: '600' },
  postValidBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
    marginTop: 10,
  },
  postValidBtnText: { fontSize: 14, fontWeight: '800', color: colors.textWhite },
  postedCard: { alignItems: 'center', padding: 24 },
  postedTitle: { fontSize: 18, fontWeight: '800', color: colors.navy, marginTop: 12 },
  postedSub: { fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: 6, lineHeight: 18 },
  postedDoneBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: radii.pill,
    marginTop: 16,
  },
  postedDoneBtnText: { color: colors.textWhite, fontSize: 13, fontWeight: '700' },
});

