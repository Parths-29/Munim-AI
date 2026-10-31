import React, { useState } from 'react';
import {
  View,
  Text,
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
import { useDemoData, DemoPayment, DemoCustomer } from '@/context/DemoDataContext';

interface PaytmPaymentReviewScreenProps {
  onBack?: () => void;
}

export const PaytmPaymentReviewScreen: React.FC<PaytmPaymentReviewScreenProps> = ({ onBack }) => {
  const {
    payments,
    customers,
    allocatePayment,
    addSyntheticPayment,
  } = useDemoData();

  const [activeSection, setActiveSection] = useState<'needs_review' | 'recorded'>('needs_review');
  const [selectedPayment, setSelectedPayment] = useState<DemoPayment | null>(null);

  // Allocation Modal state
  const [allocationModalVisible, setAllocationModalVisible] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>(customers[0]?.id || '');
  const [allocationReviewing, setAllocationReviewing] = useState(false);
  const [allocationError, setAllocationError] = useState<string | null>(null);

  const needsReviewList = payments.filter((p) => p.reviewStatus === 'NEEDS_REVIEW');
  const recordedList = payments.filter((p) => p.reviewStatus !== 'NEEDS_REVIEW');

  const targetCustomer = customers.find((c) => c.id === selectedCustomerId);

  // Handler: Confirm Allocation
  const handleConfirmAllocation = async () => {
    if (!selectedPayment || !targetCustomer) return;
    setAllocationError(null);

    if (selectedPayment.status !== 'SUCCESS') {
      setAllocationError('Only successful payments can be allocated to customer dues.');
      return;
    }

    if (selectedPayment.amountPaise > targetCustomer.amountDuePaise) {
      setAllocationError(
        `Payment amount ₹${(selectedPayment.amountPaise / 100).toFixed(2)} exceeds ${targetCustomer.name}'s current due of ₹${(targetCustomer.amountDuePaise / 100).toFixed(2)}. Excessive allocation is blocked.`
      );
      return;
    }

    try {
      await allocatePayment(selectedPayment.id, targetCustomer.id);
      setAllocationModalVisible(false);
      setAllocationReviewing(false);
      setSelectedPayment(null);
      Alert.alert(
        'Allocation Recorded',
        `Successfully allocated ₹${(selectedPayment.amountPaise / 100).toFixed(2)} to ${targetCustomer.name}. Customer debt reduced safely.`
      );
    } catch (err: unknown) {
      setAllocationError(err instanceof Error ? err.message : 'Allocation failed.');
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {onBack && (
          <TouchableOpacity style={styles.backBtn} onPress={onBack}>
            <Ionicons name="arrow-back" size={20} color={colors.navy} />
            <Text style={styles.backBtnText}>Back</Text>
          </TouchableOpacity>
        )}

        {/* Top Disclaimer Card */}
        <PaytmCard variant="paleBlue" style={styles.disclaimerCard}>
          <View style={styles.disclaimerRow}>
            <Ionicons name="shield-checkmark" size={20} color={colors.navy} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <View style={styles.badgeRow}>
                <Text style={styles.disclaimerTitle}>Payment-to-Ledger Reconciliation</Text>
                <Badge label="Simulated" variant="simulated" />
              </View>
              <Text style={styles.disclaimerDesc}>
                Mock UPI payments require merchant verification. Allocating links cash received to a customer's udhaar without double-counting.
              </Text>
            </View>
          </View>
        </PaytmCard>

        {/* Section Tabs */}
        <View style={styles.tabBar}>
          <TouchableOpacity
            style={[styles.tabItem, activeSection === 'needs_review' && styles.tabItemActive]}
            onPress={() => setActiveSection('needs_review')}
          >
            <Text style={[styles.tabText, activeSection === 'needs_review' && styles.tabTextActive]}>
              Needs Review ({needsReviewList.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeSection === 'recorded' && styles.tabItemActive]}
            onPress={() => setActiveSection('recorded')}
          >
            <Text style={[styles.tabText, activeSection === 'recorded' && styles.tabTextActive]}>
              Recorded Events ({recordedList.length})
            </Text>
          </TouchableOpacity>
        </View>

        {/* ── LIST ITEMS ────────────────────────────────────────────── */}
        {activeSection === 'needs_review' ? (
          needsReviewList.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="checkmark-done-circle" size={48} color={colors.success} />
              <Text style={styles.emptyTitle}>Review Queue Clear</Text>
              <Text style={styles.emptySub}>All simulated UPI payments have been matched or allocated.</Text>
            </View>
          ) : (
            needsReviewList.map((payment) => (
              <PaytmCard key={payment.id} style={styles.paymentCard}>
                <View style={styles.paymentRow}>
                  <View style={styles.paymentIconCircle}>
                    <Ionicons name="qr-code" size={22} color={colors.navy} />
                  </View>

                  <View style={{ flex: 1, marginHorizontal: 12 }}>
                    <View style={styles.amountBadgeRow}>
                      <Text style={styles.paymentAmount}>₹{(payment.amountPaise / 100).toFixed(2)}</Text>
                      <Badge label="Needs Review" variant="warning" />
                    </View>
                    <Text style={styles.payerRef}>Ref: {payment.payerRef}</Text>
                    <Text style={styles.paymentTime}>{payment.timestamp} · Status: {payment.status}</Text>
                  </View>
                </View>

                {/* Reason review is needed */}
                <View style={styles.reasonBox}>
                  <Ionicons name="information-circle-outline" size={14} color={colors.textSecondary} />
                  <Text style={styles.reasonText}>
                    No exact payer token mapping found. Merchant confirmation required to link debt.
                  </Text>
                </View>

                <TouchableOpacity
                  style={styles.allocateActionBtn}
                  onPress={() => {
                    setSelectedPayment(payment);
                    setAllocationReviewing(false);
                    setAllocationError(null);
                    setAllocationModalVisible(true);
                  }}
                >
                  <Text style={styles.allocateActionBtnText}>Record Allocation to Customer →</Text>
                </TouchableOpacity>
              </PaytmCard>
            ))
          )
        ) : (
          recordedList.map((payment) => (
            <PaytmCard key={payment.id} style={styles.paymentCard}>
              <View style={styles.paymentRow}>
                <View style={[styles.paymentIconCircle, { backgroundColor: colors.successSurface }]}>
                  <Ionicons name="checkmark-circle" size={22} color={colors.jamaGreen} />
                </View>
                <View style={{ flex: 1, marginHorizontal: 12 }}>
                  <View style={styles.amountBadgeRow}>
                    <Text style={styles.paymentAmount}>₹{(payment.amountPaise / 100).toFixed(2)}</Text>
                    <Badge label="Allocated" variant="success" />
                  </View>
                  <Text style={styles.payerRef}>Ref: {payment.payerRef}</Text>
                  <Text style={styles.paymentTime}>
                    Allocated to {payment.allocatedToCustomerName || 'Customer'} · {payment.timestamp}
                  </Text>
                </View>
              </View>
            </PaytmCard>
          ))
        )}

        {/* ── DEMO CONTROLS SECTION ─────────────────────────────────── */}
        <View style={styles.demoControlSection}>
          <Text style={styles.demoControlHeading}>Demo Controls (Testing Only)</Text>
          <Text style={styles.demoControlSub}>
            Inject simulated payments to test the review and allocation flow.
          </Text>

          <View style={styles.demoButtonRow}>
            <TouchableOpacity
              style={styles.demoAddBtn}
              onPress={() => addSyntheticPayment(30000)} // ₹300 per Section 15
            >
              <Ionicons name="add" size={16} color={colors.navy} />
              <Text style={styles.demoAddBtnText}>Add Synthetic ₹300 Payment</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.demoAddBtn}
              onPress={() => addSyntheticPayment(50000)} // ₹500
            >
              <Ionicons name="add" size={16} color={colors.navy} />
              <Text style={styles.demoAddBtnText}>Add Synthetic ₹500 Payment</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* ── MODAL: ALLOCATE PAYMENT TO CUSTOMER ─────────────────────── */}
      <Modal visible={allocationModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Confirm Payment Allocation</Text>
              <TouchableOpacity onPress={() => setAllocationModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <Badge label="Simulated payment" variant="simulated" />

            {selectedPayment && (
              <View style={styles.paymentSummaryCard}>
                <Text style={styles.paymentSummaryLabel}>Payment Received (UPI)</Text>
                <Text style={styles.paymentSummaryAmount}>₹{(selectedPayment.amountPaise / 100).toFixed(2)}</Text>
                <Text style={styles.paymentSummaryRef}>Ref: {selectedPayment.payerRef}</Text>
              </View>
            )}

            {allocationError && (
              <View style={styles.errorAlert}>
                <Ionicons name="alert-circle" size={16} color={colors.error} />
                <Text style={styles.errorAlertText}>{allocationError}</Text>
              </View>
            )}

            {!allocationReviewing ? (
              <>
                <Text style={styles.selectCustomerLabel}>Select Customer to Settle Debt:</Text>
                <View style={styles.customerSelector}>
                  {customers.map((c) => {
                    const isSelected = c.id === selectedCustomerId;
                    return (
                      <TouchableOpacity
                        key={c.id}
                        style={[styles.customerSelectOption, isSelected && styles.customerSelectOptionActive]}
                        onPress={() => setSelectedCustomerId(c.id)}
                      >
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.custOptionName, isSelected && styles.custOptionNameActive]}>
                            {c.name}
                          </Text>
                          <Text style={styles.custOptionDue}>Current Due: ₹{(c.amountDuePaise / 100).toFixed(2)}</Text>
                        </View>
                        {isSelected && <Ionicons name="checkmark-circle" size={20} color={colors.primaryCyan} />}
                      </TouchableOpacity>
                    );
                  })}
                </View>

                <TouchableOpacity
                  style={styles.reviewAllocationBtn}
                  onPress={() => {
                    if (!targetCustomer || !selectedPayment) return;
                    if (selectedPayment.amountPaise > targetCustomer.amountDuePaise) {
                      setAllocationError(
                        `Payment amount ₹${(selectedPayment.amountPaise / 100).toFixed(2)} cannot exceed current due ₹${(targetCustomer.amountDuePaise / 100).toFixed(2)}.`
                      );
                      return;
                    }
                    setAllocationReviewing(true);
                  }}
                >
                  <Text style={styles.reviewAllocationBtnText}>Review Allocation Slip →</Text>
                </TouchableOpacity>
              </>
            ) : (
              /* Review State */
              <View style={styles.allocationReviewBox}>
                <Badge label="Not saved yet" variant="notSaved" />
                <Text style={styles.reviewAmountText}>
                  ₹{(selectedPayment ? selectedPayment.amountPaise / 100 : 0).toFixed(2)}
                </Text>
                <Text style={styles.reviewTargetName}>Allocating to: {targetCustomer?.name}</Text>

                <View style={styles.balanceDiffRow}>
                  <Text style={styles.balanceBefore}>
                    Current Due: ₹{((targetCustomer?.amountDuePaise || 0) / 100).toFixed(2)}
                  </Text>
                  <Ionicons name="arrow-forward" size={14} color={colors.textSecondary} style={{ marginHorizontal: 6 }} />
                  <Text style={styles.balanceAfter}>
                    Proposed Due: ₹{Math.max(0, ((targetCustomer?.amountDuePaise || 0) - (selectedPayment?.amountPaise || 0)) / 100).toFixed(2)}
                  </Text>
                </View>

                <View style={styles.modalBtnRow}>
                  <TouchableOpacity
                    style={styles.modalEditBtn}
                    onPress={() => setAllocationReviewing(false)}
                  >
                    <Text style={styles.modalEditBtnText}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.modalConfirmBtn}
                    onPress={handleConfirmAllocation}
                  >
                    <Text style={styles.modalConfirmBtnText}>Confirm Allocation</Text>
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
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: { flex: 1 },
  content: {
    padding: spacing.screenPadding,
    paddingBottom: 40,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  backBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.navy,
  },
  disclaimerCard: {
    marginBottom: 14,
  },
  disclaimerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  badgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  disclaimerTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.navy,
  },
  disclaimerDesc: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    padding: 4,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tabItem: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: radii.pill,
  },
  tabItemActive: {
    backgroundColor: colors.paleBlue,
  },
  tabText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.navy,
    fontWeight: '800',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 36,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.navy,
    marginTop: 10,
  },
  emptySub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
    textAlign: 'center',
  },
  paymentCard: {
    marginBottom: 10,
    padding: 14,
  },
  paymentRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  paymentIconCircle: {
    width: 44,
    height: 44,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  amountBadgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  paymentAmount: {
    fontSize: 17,
    fontWeight: '900',
    color: colors.navy,
  },
  payerRef: {
    fontSize: 12,
    color: colors.textMain,
    fontWeight: '600',
    marginTop: 2,
  },
  paymentTime: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  reasonBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 8,
    marginTop: 10,
    gap: 6,
  },
  reasonText: {
    fontSize: 11,
    color: colors.textSecondary,
    flex: 1,
  },
  allocateActionBtn: {
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
    alignItems: 'flex-end',
  },
  allocateActionBtnText: {
    fontSize: 12,
    fontWeight: '800',
    color: colors.primaryCyan,
  },
  demoControlSection: {
    marginTop: 20,
    padding: 14,
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  demoControlHeading: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.navy,
  },
  demoControlSub: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: 10,
  },
  demoButtonRow: {
    flexDirection: 'row',
    gap: 8,
  },
  demoAddBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.paleBlue,
    paddingVertical: 8,
    borderRadius: radii.button,
    borderWidth: 1,
    borderColor: '#CCE7F6',
    gap: 4,
  },
  demoAddBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.navy,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 46, 110, 0.45)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.card,
    borderTopRightRadius: radii.card,
    padding: 20,
    ...shadows.medium,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.navy,
  },
  paymentSummaryCard: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 12,
    marginVertical: 12,
    alignItems: 'center',
  },
  paymentSummaryLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  paymentSummaryAmount: {
    fontSize: 26,
    fontWeight: '900',
    color: colors.navy,
    marginVertical: 2,
  },
  paymentSummaryRef: {
    fontSize: 11,
    color: colors.textMuted,
  },
  selectCustomerLabel: {
    fontSize: 12,
    fontWeight: '800',
    color: colors.navy,
    marginBottom: 8,
  },
  customerSelector: {
    gap: 6,
    marginBottom: 14,
  },
  customerSelectOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderRadius: radii.cardSmall,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  customerSelectOptionActive: {
    borderColor: colors.primaryCyan,
    backgroundColor: colors.paleBlue,
  },
  custOptionName: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textMain,
  },
  custOptionNameActive: {
    color: colors.navy,
    fontWeight: '800',
  },
  custOptionDue: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 1,
  },
  reviewAllocationBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
    marginTop: 4,
  },
  reviewAllocationBtnText: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.textWhite,
  },
  allocationReviewBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.card,
    padding: 16,
    alignItems: 'center',
    marginTop: 10,
  },
  reviewAmountText: {
    fontSize: 28,
    fontWeight: '900',
    color: colors.navy,
    marginVertical: 6,
  },
  reviewTargetName: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textMain,
  },
  balanceDiffRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 10,
  },
  balanceBefore: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  balanceAfter: {
    fontSize: 12,
    fontWeight: '800',
    color: colors.success,
  },
  modalBtnRow: {
    flexDirection: 'row',
    gap: 10,
    width: '100%',
    marginTop: 6,
  },
  modalEditBtn: {
    flex: 1,
    backgroundColor: '#F1F5F9',
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  modalEditBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  modalConfirmBtn: {
    flex: 2,
    backgroundColor: colors.navy,
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  modalConfirmBtnText: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.textWhite,
  },
  errorAlert: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.errorSurface,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginBottom: 10,
    gap: 6,
  },
  errorAlertText: {
    fontSize: 12,
    color: colors.error,
    fontWeight: '600',
    flex: 1,
  },
});

