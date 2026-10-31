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

type ScanFlowStep = 'CAPTURE' | 'PROCESSING' | 'EDITABLE_DRAFT' | 'REVIEW' | 'RECEIPT';

interface InvoiceScanScreenProps {
  onBack?: () => void;
  onDone?: () => void;
}

export const InvoiceScanScreen: React.FC<InvoiceScanScreenProps> = ({ onBack, onDone }) => {
  const { invoiceDrafts, confirmInvoiceDraft } = useDemoData();
  const [step, setStep] = useState<ScanFlowStep>('EDITABLE_DRAFT');

  // Using demo draft from context
  const draft = invoiceDrafts[0];

  const handleSimulateScan = () => {
    setStep('PROCESSING');
    setTimeout(() => {
      setStep('EDITABLE_DRAFT');
    }, 1200);
  };

  const handleProceedToReview = () => {
    setStep('REVIEW');
  };

  const handleConfirmPosting = () => {
    if (draft) {
      confirmInvoiceDraft(draft.id);
      setStep('RECEIPT');
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {onBack && step !== 'RECEIPT' && (
          <TouchableOpacity style={styles.backBtn} onPress={onBack}>
            <Ionicons name="arrow-back" size={20} color={colors.navy} />
            <Text style={styles.backBtnText}>Back</Text>
          </TouchableOpacity>
        )}

        {/* ── STEP: CAPTURE / UPLOAD ─────────────────────────────────── */}
        {step === 'CAPTURE' && (
          <View style={styles.captureContainer}>
            <View style={styles.cameraBox}>
              <Ionicons name="camera-outline" size={54} color={colors.navy} />
              <Text style={styles.cameraTitle}>Scan Wholesale Supplier Bill</Text>
              <Text style={styles.cameraSub}>Point camera at the printed or handwritten invoice</Text>
            </View>

            <View style={styles.captureBtnRow}>
              <TouchableOpacity style={styles.captureBtn} onPress={handleSimulateScan}>
                <Ionicons name="camera" size={20} color={colors.textWhite} />
                <Text style={styles.captureBtnText}>Capture Photo (Demo)</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.manualEntryBtn} onPress={() => setStep('EDITABLE_DRAFT')}>
                <Text style={styles.manualEntryBtnText}>Manual Entry Fallback</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* ── STEP: PROCESSING ───────────────────────────────────────── */}
        {step === 'PROCESSING' && (
          <View style={styles.centerProcessing}>
            <ActivityIndicator size="large" color={colors.primaryCyan} />
            <Text style={styles.processingTitle}>Extracting Bill Line Items...</Text>
            <Text style={styles.processingSub}>Validating product aliases, unit conversions, and invoice totals.</Text>
          </View>
        )}

        {/* ── STEP: EDITABLE DRAFT ───────────────────────────────────── */}
        {step === 'EDITABLE_DRAFT' && draft && (
          <>
            <View style={styles.draftHeaderRow}>
              <View>
                <Text style={styles.pageTitle}>Supplier Bill Inward Draft</Text>
                <Text style={styles.pageSub}>Review items extracted before posting to stock & payable</Text>
              </View>
              <Badge label="Draft — not posted" variant="draft" />
            </View>

            {/* Validation Warnings */}
            {draft.issues.length > 0 && (
              <View style={styles.issuesBanner}>
                <Ionicons name="alert-circle" size={16} color={colors.warning} />
                <View style={{ flex: 1, marginLeft: 6 }}>
                  {draft.issues.map((iss, i) => (
                    <Text key={i} style={styles.issueText}>{iss}</Text>
                  ))}
                </View>
              </View>
            )}

            {/* Invoice Meta Card */}
            <PaytmCard style={styles.metaCard}>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Supplier:</Text>
                <Text style={styles.metaValue}>{draft.supplierName}</Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Invoice Number:</Text>
                <Text style={styles.metaValue}>{draft.invoiceNumber}</Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Bill Date:</Text>
                <Text style={styles.metaValue}>{draft.date}</Text>
              </View>
            </PaytmCard>

            {/* Items Table Card */}
            <Text style={styles.tableHeading}>Bill Line Items ({draft.items.length})</Text>
            <PaytmCard style={styles.itemsCard}>
              {draft.items.map((item, index) => (
                <View key={index}>
                  <View style={styles.itemRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.itemName}>{item.productName}</Text>
                      <Text style={styles.itemQty}>
                        Quantity: {item.quantity} {item.unit}s @ ₹{(item.unitCostPaise / 100).toFixed(2)}
                      </Text>
                    </View>
                    <Text style={styles.itemTotal}>₹{(item.totalPaise / 100).toFixed(2)}</Text>
                  </View>
                  {index < draft.items.length - 1 && <View style={styles.itemDivider} />}
                </View>
              ))}

              <View style={styles.billTotalRow}>
                <Text style={styles.billTotalLabel}>Grand Total (Payable):</Text>
                <Text style={styles.billTotalValue}>₹{(draft.totalPaise / 100).toFixed(2)}</Text>
              </View>
            </PaytmCard>

            <TouchableOpacity style={styles.proceedReviewBtn} onPress={handleProceedToReview}>
              <Text style={styles.proceedReviewBtnText}>Proceed to Final Review →</Text>
            </TouchableOpacity>
          </>
        )}

        {/* ── STEP: REVIEW & CONFIRM ─────────────────────────────────── */}
        {step === 'REVIEW' && draft && (
          <PaytmCard style={styles.finalReviewCard}>
            <View style={styles.reviewHeader}>
              <Text style={styles.finalReviewTitle}>Confirm Stock Inward & Payable</Text>
              <Badge label="Confirmation Required" variant="warning" />
            </View>

            <View style={styles.impactBox}>
              <Text style={styles.impactBoxHeading}>Exactly what will change upon confirmation:</Text>
              <View style={styles.impactBulletRow}>
                <Ionicons name="checkmark-circle" size={16} color={colors.success} />
                <Text style={styles.impactBulletText}>
                  Stock Inward: +24 packs Maggi, +48 packs Parle-G added to inventory.
                </Text>
              </View>
              <View style={styles.impactBulletRow}>
                <Ionicons name="checkmark-circle" size={16} color={colors.success} />
                <Text style={styles.impactBulletText}>
                  Supplier Payable: ₹{(draft.totalPaise / 100).toFixed(2)} added to Krishna FMCG balance.
                </Text>
              </View>
            </View>

            <View style={styles.actionBtnRow}>
              <TouchableOpacity style={styles.backEditBtn} onPress={() => setStep('EDITABLE_DRAFT')}>
                <Text style={styles.backEditBtnText}>Edit Draft</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.confirmPostBtn} onPress={handleConfirmPosting}>
                <Text style={styles.confirmPostBtnText}>Confirm & Post Inward</Text>
              </TouchableOpacity>
            </View>
          </PaytmCard>
        )}

        {/* ── STEP: RECEIPT ─────────────────────────────────────────── */}
        {step === 'RECEIPT' && draft && (
          <PaytmCard style={styles.receiptCard}>
            <Ionicons name="checkmark-circle" size={54} color={colors.success} />
            <Text style={styles.receiptTitle}>Stock Inward Posted Successfully</Text>
            <Text style={styles.receiptRef}>Receipt Reference: #{draft.invoiceNumber}</Text>

            <View style={styles.receiptSummaryBox}>
              <Text style={styles.receiptSummaryText}>
                Inventory balances updated. Supplier khata updated with ₹{(draft.totalPaise / 100).toFixed(2)} payable.
              </Text>
            </View>

            <TouchableOpacity style={styles.doneBtn} onPress={onDone || onBack}>
              <Text style={styles.doneBtnText}>Return to Dashboard</Text>
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
  captureContainer: { alignItems: 'center', paddingVertical: 30 },
  cameraBox: {
    width: '100%',
    height: 240,
    borderRadius: radii.card,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: colors.primaryCyan,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    marginBottom: 20,
  },
  cameraTitle: { fontSize: 16, fontWeight: '800', color: colors.navy, marginTop: 10 },
  cameraSub: { fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: 4 },
  captureBtnRow: { width: '100%', gap: 10 },
  captureBtn: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    gap: 8,
  },
  captureBtnText: { fontSize: 14, fontWeight: '800', color: colors.textWhite },
  manualEntryBtn: {
    backgroundColor: colors.surface,
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  manualEntryBtnText: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
  centerProcessing: { alignItems: 'center', paddingVertical: 60 },
  processingTitle: { fontSize: 16, fontWeight: '800', color: colors.navy, marginTop: 14 },
  processingSub: { fontSize: 12, color: colors.textSecondary, marginTop: 4, textAlign: 'center' },
  draftHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  pageTitle: { fontSize: 17, fontWeight: '800', color: colors.navy },
  pageSub: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  issuesBanner: {
    flexDirection: 'row',
    backgroundColor: colors.warningSurface,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  issueText: { fontSize: 11, color: '#92400E', fontWeight: '600' },
  metaCard: { marginBottom: 12, padding: 12 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  metaLabel: { fontSize: 12, color: colors.textSecondary },
  metaValue: { fontSize: 13, fontWeight: '700', color: colors.textMain },
  tableHeading: { fontSize: 14, fontWeight: '800', color: colors.navy, marginBottom: 8 },
  itemsCard: { padding: 12, marginBottom: 16 },
  itemRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8 },
  itemName: { fontSize: 13, fontWeight: '700', color: colors.textMain },
  itemQty: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  itemTotal: { fontSize: 14, fontWeight: '800', color: colors.navy },
  itemDivider: { height: 1, backgroundColor: colors.borderSubtle },
  billTotalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 10,
    marginTop: 6,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  billTotalLabel: { fontSize: 14, fontWeight: '800', color: colors.navy },
  billTotalValue: { fontSize: 18, fontWeight: '900', color: colors.navy },
  proceedReviewBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  proceedReviewBtnText: { fontSize: 14, fontWeight: '800', color: colors.textWhite },
  finalReviewCard: { padding: 16 },
  reviewHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  finalReviewTitle: { fontSize: 16, fontWeight: '800', color: colors.navy },
  impactBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 14,
    marginBottom: 16,
  },
  impactBoxHeading: { fontSize: 12, fontWeight: '800', color: colors.navy, marginBottom: 8 },
  impactBulletRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginVertical: 3 },
  impactBulletText: { fontSize: 12, color: colors.textMain, flex: 1 },
  actionBtnRow: { flexDirection: 'row', gap: 10 },
  backEditBtn: { flex: 1, backgroundColor: '#F1F5F9', paddingVertical: 12, borderRadius: radii.button, alignItems: 'center' },
  backEditBtnText: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
  confirmPostBtn: { flex: 2, backgroundColor: colors.navy, paddingVertical: 12, borderRadius: radii.button, alignItems: 'center' },
  confirmPostBtnText: { fontSize: 13, fontWeight: '800', color: colors.textWhite },
  receiptCard: { alignItems: 'center', padding: 24 },
  receiptTitle: { fontSize: 18, fontWeight: '800', color: colors.navy, marginTop: 12, textAlign: 'center' },
  receiptRef: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },
  receiptSummaryBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 12,
    marginVertical: 16,
    width: '100%',
  },
  receiptSummaryText: { fontSize: 12, color: colors.textMain, textAlign: 'center', lineHeight: 18 },
  doneBtn: { backgroundColor: colors.navy, paddingVertical: 12, paddingHorizontal: 28, borderRadius: radii.pill },
  doneBtnText: { color: colors.textWhite, fontSize: 13, fontWeight: '700' },
});

