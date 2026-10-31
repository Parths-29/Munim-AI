import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Modal,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { Badge } from '@/components/common/Badge';
import { useDemoData, DemoSupplier } from '@/context/DemoDataContext';

interface SupplierScreenProps {
  onBack?: () => void;
  onOpenScanBill?: () => void;
}

export const SupplierScreen: React.FC<SupplierScreenProps> = ({ onBack, onOpenScanBill }) => {
  const { suppliers, recordSupplierPayment } = useDemoData();

  const [selectedSupplier, setSelectedSupplier] = useState<DemoSupplier | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Payment modal state
  const [payModalVisible, setPayModalVisible] = useState(false);
  const [payAmountInput, setPayAmountInput] = useState('');
  const [payNote, setPayNote] = useState('');
  const [payReviewing, setPayReviewing] = useState(false);

  const filteredSuppliers = suppliers.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalPayablesPaise = suppliers.reduce((sum, s) => sum + s.payablePaise, 0);

  const handleConfirmSupplierPayment = () => {
    if (!selectedSupplier) return;
    const amount = parseFloat(payAmountInput);
    if (isNaN(amount) || amount <= 0) {
      Alert.alert('Invalid', 'Enter valid amount.');
      return;
    }
    const amountPaise = Math.round(amount * 100);
    recordSupplierPayment(selectedSupplier.id, amountPaise);

    setSelectedSupplier((prev) =>
      prev ? { ...prev, payablePaise: Math.max(0, prev.payablePaise - amountPaise) } : null
    );
    setPayModalVisible(false);
    setPayReviewing(false);
    setPayAmountInput('');
    setPayNote('');
    Alert.alert(
      'Payment Event Recorded',
      `Accounting entry saved: ₹${amount.toFixed(2)} recorded for ${selectedSupplier.name}. (Note: This is an internal accounting record, not a bank transfer).`
    );
  };

  return (
    <View style={styles.container}>
      {selectedSupplier ? (
        /* ── SUPPLIER DETAIL VIEW ───────────────────────────────────── */
        <ScrollView style={styles.detailScroll} contentContainerStyle={styles.detailContent}>
          <TouchableOpacity style={styles.backBtn} onPress={() => setSelectedSupplier(null)}>
            <Ionicons name="arrow-back" size={20} color={colors.navy} />
            <Text style={styles.backBtnText}>All Suppliers</Text>
          </TouchableOpacity>

          <PaytmCard style={styles.supplierDetailCard}>
            <View style={styles.supplierHeader}>
              <View style={styles.supplierAvatarLarge}>
                <Ionicons name="business" size={26} color={colors.navy} />
              </View>
              <View style={{ flex: 1, marginLeft: 14 }}>
                <Text style={styles.detailName}>{selectedSupplier.name}</Text>
                <Text style={styles.detailContact}>{selectedSupplier.contact}</Text>
                <Text style={styles.detailLastInv}>Last Bill: {selectedSupplier.lastInvoiceDate}</Text>
              </View>
            </View>

            {/* Payable Banner */}
            <View style={styles.payableBox}>
              <Text style={styles.payableLabel}>Amount Owed to Supplier (Payable)</Text>
              <Text style={styles.payableAmount}>₹{(selectedSupplier.payablePaise / 100).toFixed(2)}</Text>
              <Text style={styles.payableSub}>Keep supplier payables separate from customer dues.</Text>
            </View>

            {/* Actions */}
            <View style={styles.supplierActionRow}>
              <TouchableOpacity
                style={styles.recordPayBtn}
                onPress={() => {
                  setPayReviewing(false);
                  setPayModalVisible(true);
                }}
              >
                <Ionicons name="cash-outline" size={18} color={colors.textWhite} />
                <Text style={styles.recordPayBtnText}>Record Supplier Payment</Text>
              </TouchableOpacity>

              {onOpenScanBill && (
                <TouchableOpacity
                  style={styles.scanBillBtn}
                  onPress={onOpenScanBill}
                >
                  <Ionicons name="document-text-outline" size={18} color={colors.navy} />
                  <Text style={styles.scanBillBtnText}>Scan Inward Bill</Text>
                </TouchableOpacity>
              )}
            </View>
          </PaytmCard>

          {/* History */}
          <Text style={styles.historyHeading}>Invoices & Accounting History</Text>
          <PaytmCard style={styles.historyCard}>
            <View style={styles.historyItemRow}>
              <Ionicons name="receipt-outline" size={18} color={colors.navy} />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.historyItemTitle}>Inward Delivery Bill #INV-2026-904</Text>
                <Text style={styles.historyItemDate}>31 Oct 2026 · FMCG stock verified</Text>
              </View>
              <Text style={styles.historyItemAmt}>+ ₹696.00</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.historyItemRow}>
              <Ionicons name="checkmark-done" size={18} color={colors.success} />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.historyItemTitle}>Supplier Settlement Payment</Text>
                <Text style={styles.historyItemDate}>28 Oct 2026 · Cash outflow</Text>
              </View>
              <Text style={[styles.historyItemAmt, { color: colors.success }]}>- ₹5,000.00</Text>
            </View>
          </PaytmCard>
        </ScrollView>
      ) : (
        /* ── SUPPLIER LIST VIEW ─────────────────────────────────────── */
        <ScrollView style={styles.listScroll} contentContainerStyle={styles.listContent}>
          {onBack && (
            <TouchableOpacity style={styles.backBtn} onPress={onBack}>
              <Ionicons name="arrow-back" size={20} color={colors.navy} />
              <Text style={styles.backBtnText}>Back to More</Text>
            </TouchableOpacity>
          )}

          {/* Banner */}
          <PaytmCard variant="paleBlue" style={styles.topBanner}>
            <View style={styles.topBannerRow}>
              <View>
                <Text style={styles.topBannerLabel}>TOTAL SUPPLIER PAYABLES</Text>
                <Text style={styles.topBannerAmount}>
                  ₹{(totalPayablesPaise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </Text>
              </View>
              <Badge label="Accounts Payable" variant="neutral" />
            </View>
            <Text style={styles.topBannerSub}>{suppliers.length} active wholesale vendor accounts</Text>
          </PaytmCard>

          {/* Search Bar */}
          <View style={styles.searchBar}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput
              style={styles.searchInput}
              value={searchQuery}
              onChangeText={setSearchQuery}
              placeholder="Search suppliers by name..."
              placeholderTextColor={colors.textMuted}
            />
          </View>

          {/* List */}
          <Text style={styles.listHeading}>Registered Suppliers</Text>
          {filteredSuppliers.map((supp) => (
            <TouchableOpacity
              key={supp.id}
              onPress={() => setSelectedSupplier(supp)}
              activeOpacity={0.7}
            >
              <PaytmCard style={styles.supplierRowCard}>
                <View style={styles.supplierRow}>
                  <View style={styles.supplierIconCircle}>
                    <Ionicons name="business-outline" size={20} color={colors.navy} />
                  </View>
                  <View style={{ flex: 1, marginHorizontal: 12 }}>
                    <Text style={styles.suppName}>{supp.name}</Text>
                    <Text style={styles.suppContact}>{supp.contact}</Text>
                    <Text style={styles.suppLastInv}>Last Bill: {supp.lastInvoiceDate}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={styles.payableDueLabel}>Payable</Text>
                    <Text style={styles.payableDueAmount}>
                      ₹{(supp.payablePaise / 100).toFixed(2)}
                    </Text>
                    <Ionicons name="chevron-forward" size={16} color={colors.textMuted} style={{ marginTop: 4 }} />
                  </View>
                </View>
              </PaytmCard>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* ── MODAL: RECORD SUPPLIER PAYMENT ──────────────────────────── */}
      <Modal visible={payModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Record Supplier Payment</Text>
              <TouchableOpacity onPress={() => setPayModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <View style={styles.accountingNotice}>
              <Ionicons name="alert-circle-outline" size={18} color={colors.navy} />
              <Text style={styles.accountingNoticeText}>
                Accounting Event Only: Recording a supplier payment logs an outflow in shop accounts. It does NOT initiate a bank or UPI transfer.
              </Text>
            </View>

            {selectedSupplier && (
              <View style={styles.supplierPayBanner}>
                <Text style={styles.suppPayBannerName}>{selectedSupplier.name}</Text>
                <Text style={styles.suppPayBannerDue}>
                  Current Payable: ₹{(selectedSupplier.payablePaise / 100).toFixed(2)}
                </Text>
              </View>
            )}

            {!payReviewing ? (
              <>
                <Text style={styles.inputLabel}>Enter Payment Amount (₹) *</Text>
                <TextInput
                  style={[styles.modalTextInput, styles.amountInputBig]}
                  placeholder="₹ 0.00"
                  keyboardType="numeric"
                  value={payAmountInput}
                  onChangeText={setPayAmountInput}
                />

                <Text style={styles.inputLabel}>Payment Reference / Note</Text>
                <TextInput
                  style={styles.modalTextInput}
                  placeholder="e.g. Cash paid to delivery agent / Cheque #123"
                  value={payNote}
                  onChangeText={setPayNote}
                />

                <TouchableOpacity
                  style={styles.submitModalBtn}
                  onPress={() => {
                    const amt = parseFloat(payAmountInput);
                    if (isNaN(amt) || amt <= 0) {
                      Alert.alert('Invalid', 'Enter valid amount.');
                      return;
                    }
                    setPayReviewing(true);
                  }}
                >
                  <Text style={styles.submitModalBtnText}>Review Accounting Slip →</Text>
                </TouchableOpacity>
              </>
            ) : (
              <View style={styles.reviewBox}>
                <Badge label="Not saved yet" variant="notSaved" />
                <Text style={styles.reviewAmountText}>₹{parseFloat(payAmountInput).toFixed(2)}</Text>
                <Text style={styles.reviewTargetName}>Payment to {selectedSupplier?.name}</Text>
                <Text style={styles.reviewDiff}>
                  Remaining Payable: ₹
                  {Math.max(
                    0,
                    ((selectedSupplier?.payablePaise || 0) - Math.round(parseFloat(payAmountInput) * 100)) / 100
                  ).toFixed(2)}
                </Text>

                <View style={styles.modalBtnRow}>
                  <TouchableOpacity
                    style={styles.modalEditBtn}
                    onPress={() => setPayReviewing(false)}
                  >
                    <Text style={styles.modalEditBtnText}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.modalConfirmBtn}
                    onPress={handleConfirmSupplierPayment}
                  >
                    <Text style={styles.modalConfirmBtnText}>Confirm Entry</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  listScroll: { flex: 1 },
  listContent: { padding: spacing.screenPadding, paddingBottom: 40 },
  detailScroll: { flex: 1 },
  detailContent: { padding: spacing.screenPadding, paddingBottom: 40 },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  backBtnText: { fontSize: 14, fontWeight: '700', color: colors.navy },
  topBanner: { marginBottom: 14 },
  topBannerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  topBannerLabel: { fontSize: 10, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.3 },
  topBannerAmount: { fontSize: 26, fontWeight: '900', color: colors.navy, marginTop: 2 },
  topBannerSub: { fontSize: 11, color: colors.textSecondary, marginTop: 4 },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radii.input,
    paddingHorizontal: 12,
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 14,
  },
  searchInput: { flex: 1, marginLeft: 8, fontSize: 13, color: colors.textMain },
  listHeading: { fontSize: 14, fontWeight: '800', color: colors.navy, marginBottom: 10 },
  supplierRowCard: { marginBottom: 8, padding: 12 },
  supplierRow: { flexDirection: 'row', alignItems: 'center' },
  supplierIconCircle: {
    width: 44,
    height: 44,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  suppName: { fontSize: 14, fontWeight: '800', color: colors.textMain },
  suppContact: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  suppLastInv: { fontSize: 10, color: colors.textMuted, marginTop: 2 },
  payableDueLabel: { fontSize: 10, color: colors.textSecondary },
  payableDueAmount: { fontSize: 15, fontWeight: '800', color: colors.navy, marginTop: 1 },
  supplierDetailCard: { marginBottom: 16 },
  supplierHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 14 },
  supplierAvatarLarge: {
    width: 54,
    height: 54,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: colors.primaryCyan,
  },
  detailName: { fontSize: 17, fontWeight: '800', color: colors.navy },
  detailContact: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  detailLastInv: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  payableBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 14,
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  payableLabel: { fontSize: 11, fontWeight: '700', color: colors.textSecondary },
  payableAmount: { fontSize: 28, fontWeight: '900', color: colors.navy, marginVertical: 4 },
  payableSub: { fontSize: 10, color: colors.textMuted },
  supplierActionRow: { flexDirection: 'row', gap: 10 },
  recordPayBtn: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.navy,
    paddingVertical: 12,
    borderRadius: radii.button,
    gap: 6,
  },
  recordPayBtnText: { fontSize: 12, fontWeight: '800', color: colors.textWhite },
  scanBillBtn: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.paleBlue,
    paddingVertical: 12,
    borderRadius: radii.button,
    gap: 6,
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  scanBillBtnText: { fontSize: 12, fontWeight: '800', color: colors.navy },
  historyHeading: { fontSize: 15, fontWeight: '800', color: colors.navy, marginBottom: 10 },
  historyCard: { padding: 12 },
  historyItemRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  historyItemTitle: { fontSize: 13, fontWeight: '700', color: colors.textMain },
  historyItemDate: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  historyItemAmt: { fontSize: 13, fontWeight: '800', color: colors.navy },
  divider: { height: 1, backgroundColor: colors.borderSubtle },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0, 46, 110, 0.45)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.card,
    borderTopRightRadius: radii.card,
    padding: 20,
    ...shadows.medium,
  },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: colors.navy },
  accountingNotice: {
    flexDirection: 'row',
    backgroundColor: colors.paleBlue,
    borderRadius: radii.cardSmall,
    padding: 10,
    gap: 8,
    marginVertical: 10,
  },
  accountingNoticeText: { fontSize: 11, color: colors.navy, flex: 1, lineHeight: 15 },
  supplierPayBanner: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginBottom: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  suppPayBannerName: { fontSize: 13, fontWeight: '800', color: colors.navy },
  suppPayBannerDue: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },
  inputLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginBottom: 6 },
  modalTextInput: {
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.input,
    paddingHorizontal: 12,
    fontSize: 14,
    color: colors.textMain,
    marginBottom: 12,
  },
  amountInputBig: { fontSize: 24, fontWeight: '800', color: colors.navy, height: 52 },
  submitModalBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
    marginTop: 4,
  },
  submitModalBtnText: { fontSize: 14, fontWeight: '800', color: colors.textWhite },
  reviewBox: { backgroundColor: colors.surfaceSubtle, borderRadius: radii.card, padding: 16, alignItems: 'center' },
  reviewAmountText: { fontSize: 28, fontWeight: '900', color: colors.navy, marginVertical: 6 },
  reviewTargetName: { fontSize: 14, fontWeight: '800', color: colors.textMain },
  reviewDiff: { fontSize: 12, color: colors.textSecondary, marginTop: 4, marginBottom: 14 },
  modalBtnRow: { flexDirection: 'row', gap: 10, width: '100%' },
  modalEditBtn: { flex: 1, backgroundColor: '#F1F5F9', paddingVertical: 12, borderRadius: radii.button, alignItems: 'center' },
  modalEditBtnText: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
  modalConfirmBtn: { flex: 2, backgroundColor: colors.navy, paddingVertical: 12, borderRadius: radii.button, alignItems: 'center' },
  modalConfirmBtnText: { fontSize: 13, fontWeight: '800', color: colors.textWhite },
});

