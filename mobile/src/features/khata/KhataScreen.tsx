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
import { useDemoData, DemoCustomer } from '@/context/DemoDataContext';

interface KhataScreenProps {
  onOpenReminders?: () => void;
}

export const KhataScreen: React.FC<KhataScreenProps> = ({ onOpenReminders }) => {
  const {
    customers,
    addCustomer,
    addCredit,
    recordJama,
    activityEvents,
  } = useDemoData();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<DemoCustomer | null>(null);

  // Modals
  const [addCustomerModalVisible, setAddCustomerModalVisible] = useState(false);
  const [newCustName, setNewCustName] = useState('');
  const [newCustPhone, setNewCustPhone] = useState('');

  const [addUdhaarModalVisible, setAddUdhaarModalVisible] = useState(false);
  const [udhaarAmountInput, setUdhaarAmountInput] = useState('');
  const [udhaarNote, setUdhaarNote] = useState('');
  const [udhaarReviewing, setUdhaarReviewing] = useState(false);

  const [recordJamaModalVisible, setRecordJamaModalVisible] = useState(false);
  const [jamaAmountInput, setJamaAmountInput] = useState('');
  const [jamaNote, setJamaNote] = useState('');
  const [jamaReviewing, setJamaReviewing] = useState(false);
  const [jamaError, setJamaError] = useState<string | null>(null);

  // Filtered customer list
  const filteredCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.phone.includes(searchQuery) ||
      c.aliases.some((a) => a.includes(searchQuery.toLowerCase()))
  );

  const totalDuesPaise = customers.reduce((sum, c) => sum + c.amountDuePaise, 0);

  // Add Customer Handler
  const handleCreateCustomer = () => {
    if (!newCustName.trim()) {
      Alert.alert('Required', 'Please enter customer name');
      return;
    }
    const created = addCustomer(newCustName.trim(), newCustPhone.trim() || '+91 98000 00000');
    setNewCustName('');
    setNewCustPhone('');
    setAddCustomerModalVisible(false);
    setSelectedCustomer(created);
  };

  // Add Udhaar Handler
  const handleConfirmUdhaar = async () => {
    if (!selectedCustomer) return;
    const amount = parseFloat(udhaarAmountInput);
    if (isNaN(amount) || amount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid rupee amount.');
      return;
    }
    const amountPaise = Math.round(amount * 100);
    const { newDuePaise } = await addCredit(selectedCustomer.id, amountPaise, udhaarNote);

    // Update selected customer local reference
    setSelectedCustomer((prev) => (prev ? { ...prev, amountDuePaise: newDuePaise } : null));
    setUdhaarAmountInput('');
    setUdhaarNote('');
    setUdhaarReviewing(false);
    setAddUdhaarModalVisible(false);
  };

  // Record Jama Handler
  const handleConfirmJama = async () => {
    if (!selectedCustomer) return;
    setJamaError(null);
    const amount = parseFloat(jamaAmountInput);
    if (isNaN(amount) || amount <= 0) {
      setJamaError('Please enter a valid rupee amount.');
      return;
    }
    const amountPaise = Math.round(amount * 100);

    if (amountPaise > selectedCustomer.amountDuePaise) {
      setJamaError(
        `Repayment ₹${amount.toFixed(2)} exceeds outstanding due ₹${(selectedCustomer.amountDuePaise / 100).toFixed(2)}. Overpayments are blocked.`
      );
      return;
    }

    try {
      const { newDuePaise } = await recordJama(selectedCustomer.id, amountPaise, jamaNote);
      setSelectedCustomer((prev) => (prev ? { ...prev, amountDuePaise: newDuePaise } : null));
      setJamaAmountInput('');
      setJamaNote('');
      setJamaReviewing(false);
      setRecordJamaModalVisible(false);
    } catch (err: unknown) {
      setJamaError(err instanceof Error ? err.message : 'Repayment failed.');
    }
  };

  return (
    <View style={styles.container}>
      {/* ── CUSTOMER DETAIL VIEW ─────────────────────────────────────── */}
      {selectedCustomer ? (
        <ScrollView style={styles.detailScroll} contentContainerStyle={styles.detailContent}>
          {/* Back to list */}
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => setSelectedCustomer(null)}
          >
            <Ionicons name="arrow-back" size={20} color={colors.navy} />
            <Text style={styles.backButtonText}>All Customers</Text>
          </TouchableOpacity>

          {/* Customer Profile Card */}
          <PaytmCard style={styles.customerProfileCard}>
            <View style={styles.profileHeader}>
              <View style={styles.profileAvatarLarge}>
                <Text style={styles.profileAvatarLargeText}>
                  {selectedCustomer.name.charAt(0).toUpperCase()}
                </Text>
              </View>
              <View style={{ flex: 1, marginLeft: 14 }}>
                <Text style={styles.customerDetailName}>{selectedCustomer.name}</Text>
                <Text style={styles.customerDetailPhone}>{selectedCustomer.phone}</Text>
                <View style={styles.aliasRow}>
                  <Text style={styles.aliasLabel}>Aliases: </Text>
                  {selectedCustomer.aliases.map((a) => (
                    <Text key={a} style={styles.aliasPill}>{a}</Text>
                  ))}
                </View>
              </View>
            </View>

            <View style={styles.balanceBox}>
              <Text style={styles.balanceBoxLabel}>Total Outstanding Amount Due</Text>
              <Text style={[styles.balanceBoxAmount, { color: selectedCustomer.amountDuePaise > 0 ? colors.udhaarRed : colors.success }]}>
                ₹{(selectedCustomer.amountDuePaise / 100).toFixed(2)}
              </Text>
              <Text style={styles.balanceBoxSub}>Derived from historical ledger entries</Text>
            </View>

            {/* Quick Actions */}
            <View style={styles.customerActionRow}>
              <TouchableOpacity
                style={[styles.primaryCustomerBtn, { backgroundColor: colors.paleBlue, borderColor: '#BAE6FD' }]}
                onPress={() => {
                  setUdhaarReviewing(false);
                  setAddUdhaarModalVisible(true);
                }}
              >
                <Ionicons name="add-circle" size={18} color={colors.navy} />
                <Text style={[styles.primaryCustomerBtnText, { color: colors.navy }]}>Add Udhaar</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.primaryCustomerBtn, { backgroundColor: colors.navy }]}
                onPress={() => {
                  setJamaError(null);
                  setJamaReviewing(false);
                  setRecordJamaModalVisible(true);
                }}
              >
                <Ionicons name="arrow-down-circle" size={18} color={colors.textWhite} />
                <Text style={[styles.primaryCustomerBtnText, { color: colors.textWhite }]}>Record Jama</Text>
              </TouchableOpacity>
            </View>

            {onOpenReminders && selectedCustomer.amountDuePaise > 0 && (
              <TouchableOpacity
                style={styles.reminderLinkBtn}
                onPress={onOpenReminders}
              >
                <Ionicons name="logo-whatsapp" size={16} color="#25D366" />
                <Text style={styles.reminderLinkText}>Review Payment Reminder Draft →</Text>
              </TouchableOpacity>
            )}
          </PaytmCard>

          {/* Customer Ledger Entries */}
          <Text style={styles.ledgerSectionTitle}>Customer Ledger History</Text>
          <PaytmCard style={styles.ledgerHistoryCard}>
            {activityEvents
              .filter((e) => e.summary.toLowerCase().includes(selectedCustomer.name.toLowerCase()))
              .map((entry, index) => (
                <View key={entry.event_id || index}>
                  <View style={styles.ledgerEntryRow}>
                    <View
                      style={[
                        styles.entryTypeIndicator,
                        entry.event_type.includes('CREDIT')
                          ? { backgroundColor: colors.errorSurface }
                          : { backgroundColor: colors.successSurface },
                      ]}
                    >
                      <Ionicons
                        name={entry.event_type.includes('CREDIT') ? 'add' : 'arrow-down'}
                        size={16}
                        color={entry.event_type.includes('CREDIT') ? colors.udhaarRed : colors.jamaGreen}
                      />
                    </View>
                    <View style={{ flex: 1, marginHorizontal: 10 }}>
                      <Text style={styles.entrySummary}>{entry.summary}</Text>
                      <Text style={styles.entryTimestamp}>
                        {new Date(entry.created_at).toLocaleString()} · {entry.source_channel}
                      </Text>
                    </View>
                    <Badge label={entry.status} variant={entry.status === 'CONFIRMED' ? 'success' : 'neutral'} />
                  </View>
                  {index < activityEvents.length - 1 && <View style={styles.ledgerDivider} />}
                </View>
              ))}
          </PaytmCard>
        </ScrollView>
      ) : (
        /* ── CUSTOMER LIST VIEW ─────────────────────────────────────── */
        <ScrollView style={styles.listScroll} contentContainerStyle={styles.listContent}>
          {/* Header Summary Banner */}
          <PaytmCard variant="paleBlue" style={styles.totalKhataCard}>
            <View style={styles.khataHeaderRow}>
              <View>
                <Text style={styles.khataTotalLabel}>TOTAL MARKET DUES (UDHAAR)</Text>
                <Text style={styles.khataTotalAmount}>₹{(totalDuesPaise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</Text>
              </View>
              <TouchableOpacity
                style={styles.addCustomerTopBtn}
                onPress={() => setAddCustomerModalVisible(true)}
              >
                <Ionicons name="person-add" size={16} color={colors.navy} />
                <Text style={styles.addCustomerTopBtnText}>Add Customer</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.khataCountSub}>{customers.length} active khata accounts</Text>
          </PaytmCard>

          {/* Search Bar */}
          <View style={styles.searchBar}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput
              style={styles.searchInput}
              value={searchQuery}
              onChangeText={setSearchQuery}
              placeholder="Search by customer name, phone, alias..."
              placeholderTextColor={colors.textMuted}
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery('')}>
                <Ionicons name="close-circle" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Customer Cards List */}
          <Text style={styles.listSectionTitle}>All Customers</Text>
          {filteredCustomers.map((cust) => (
            <TouchableOpacity
              key={cust.id}
              onPress={() => setSelectedCustomer(cust)}
              activeOpacity={0.7}
            >
              <PaytmCard style={styles.customerRowCard}>
                <View style={styles.customerRow}>
                  <View style={styles.avatarCircle}>
                    <Text style={styles.avatarInitial}>
                      {cust.name.charAt(0).toUpperCase()}
                    </Text>
                  </View>

                  <View style={{ flex: 1, marginHorizontal: 12 }}>
                    <Text style={styles.customerName}>{cust.name}</Text>
                    <Text style={styles.customerPhone}>{cust.phone}</Text>
                    <Text style={styles.customerLastActive}>Active: {cust.lastActivity}</Text>
                  </View>

                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={styles.customerDueLabel}>Due</Text>
                    <Text
                      style={[
                        styles.customerDueAmount,
                        { color: cust.amountDuePaise > 0 ? colors.udhaarRed : colors.success },
                      ]}
                    >
                      ₹{(cust.amountDuePaise / 100).toFixed(2)}
                    </Text>
                    <Ionicons name="chevron-forward" size={16} color={colors.textMuted} style={{ marginTop: 4 }} />
                  </View>
                </View>
              </PaytmCard>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* ── MODAL: ADD CUSTOMER ─────────────────────────────────────── */}
      <Modal visible={addCustomerModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalSheetHeader}>
              <Text style={styles.modalSheetTitle}>Add New Customer</Text>
              <TouchableOpacity onPress={() => setAddCustomerModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSheetSub}>
              Creates a customer profile in the shop registry. Does NOT add any debt.
            </Text>

            <Text style={styles.inputLabel}>Customer Full Name *</Text>
            <TextInput
              style={styles.modalTextInput}
              placeholder="e.g. Ramesh Verma"
              value={newCustName}
              onChangeText={setNewCustName}
            />

            <Text style={styles.inputLabel}>Mobile Number (Optional)</Text>
            <TextInput
              style={styles.modalTextInput}
              placeholder="+91 98XXX XXXXX"
              keyboardType="phone-pad"
              value={newCustPhone}
              onChangeText={setNewCustPhone}
            />

            <TouchableOpacity style={styles.submitModalBtn} onPress={handleCreateCustomer}>
              <Text style={styles.submitModalBtnText}>Create Customer Profile</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ── MODAL: ADD UDHAAR (CREDIT) ──────────────────────────────── */}
      <Modal visible={addUdhaarModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalSheetHeader}>
              <Text style={styles.modalSheetTitle}>Add Udhaar (Credit)</Text>
              <TouchableOpacity onPress={() => setAddUdhaarModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            {selectedCustomer && (
              <View style={styles.modalCustomerBanner}>
                <Text style={styles.modalCustomerBannerName}>{selectedCustomer.name}</Text>
                <Text style={styles.modalCustomerBannerDue}>
                  Current Due: ₹{(selectedCustomer.amountDuePaise / 100).toFixed(2)}
                </Text>
              </View>
            )}

            {!udhaarReviewing ? (
              <>
                <Text style={styles.inputLabel}>Enter Udhaar Amount (₹) *</Text>
                <TextInput
                  style={[styles.modalTextInput, styles.amountInputBig]}
                  placeholder="₹ 0.00"
                  keyboardType="numeric"
                  value={udhaarAmountInput}
                  onChangeText={setUdhaarAmountInput}
                />

                <Text style={styles.inputLabel}>Item / Note (Optional)</Text>
                <TextInput
                  style={styles.modalTextInput}
                  placeholder="e.g. 2 Milk packets + Biscuit"
                  value={udhaarNote}
                  onChangeText={setUdhaarNote}
                />

                <TouchableOpacity
                  style={styles.submitModalBtn}
                  onPress={() => {
                    const amt = parseFloat(udhaarAmountInput);
                    if (isNaN(amt) || amt <= 0) {
                      Alert.alert('Invalid', 'Enter a valid rupee amount.');
                      return;
                    }
                    setUdhaarReviewing(true);
                  }}
                >
                  <Text style={styles.submitModalBtnText}>Review Udhaar Slip →</Text>
                </TouchableOpacity>
              </>
            ) : (
              /* Review State before confirmation */
              <View style={styles.reviewBox}>
                <Badge label="Not saved yet" variant="notSaved" />
                <Text style={styles.reviewAmount}>₹{parseFloat(udhaarAmountInput).toFixed(2)}</Text>
                <Text style={styles.reviewCustomer}>Will be added to {selectedCustomer?.name}</Text>
                <Text style={styles.reviewNewDue}>
                  New Balance Due: ₹
                  {(
                    ((selectedCustomer?.amountDuePaise || 0) + Math.round(parseFloat(udhaarAmountInput) * 100)) /
                    100
                  ).toFixed(2)}
                </Text>

                <View style={styles.modalActionButtonsRow}>
                  <TouchableOpacity
                    style={styles.modalBackBtn}
                    onPress={() => setUdhaarReviewing(false)}
                  >
                    <Text style={styles.modalBackBtnText}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.modalConfirmBtn}
                    onPress={handleConfirmUdhaar}
                  >
                    <Text style={styles.modalConfirmBtnText}>Confirm & Post</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>
        </View>
      </Modal>

      {/* ── MODAL: RECORD JAMA (REPAYMENT) ─────────────────────────── */}
      <Modal visible={recordJamaModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalSheetHeader}>
              <Text style={styles.modalSheetTitle}>Record Jama (Repayment)</Text>
              <TouchableOpacity onPress={() => setRecordJamaModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            {selectedCustomer && (
              <View style={styles.modalCustomerBanner}>
                <Text style={styles.modalCustomerBannerName}>{selectedCustomer.name}</Text>
                <Text style={styles.modalCustomerBannerDue}>
                  Max Repayment Allowed: ₹{(selectedCustomer.amountDuePaise / 100).toFixed(2)}
                </Text>
              </View>
            )}

            {jamaError && (
              <View style={styles.errorAlertBox}>
                <Ionicons name="alert-circle" size={16} color={colors.error} />
                <Text style={styles.errorAlertText}>{jamaError}</Text>
              </View>
            )}

            {!jamaReviewing ? (
              <>
                <Text style={styles.inputLabel}>Enter Repayment Amount (₹) *</Text>
                <TextInput
                  style={[styles.modalTextInput, styles.amountInputBig]}
                  placeholder="₹ 0.00"
                  keyboardType="numeric"
                  value={jamaAmountInput}
                  onChangeText={(val) => {
                    setJamaAmountInput(val);
                    setJamaError(null);
                  }}
                />

                <Text style={styles.inputLabel}>Payment Mode / Note</Text>
                <TextInput
                  style={styles.modalTextInput}
                  placeholder="e.g. Cash received in drawer"
                  value={jamaNote}
                  onChangeText={setJamaNote}
                />

                <TouchableOpacity
                  style={[styles.submitModalBtn, { backgroundColor: colors.success }]}
                  onPress={() => {
                    const amt = parseFloat(jamaAmountInput);
                    if (isNaN(amt) || amt <= 0) {
                      setJamaError('Enter a valid rupee amount.');
                      return;
                    }
                    if (selectedCustomer && Math.round(amt * 100) > selectedCustomer.amountDuePaise) {
                      setJamaError(
                        `Amount exceeds outstanding balance ₹${(selectedCustomer.amountDuePaise / 100).toFixed(2)}.`
                      );
                      return;
                    }
                    setJamaReviewing(true);
                  }}
                >
                  <Text style={styles.submitModalBtnText}>Review Jama Slip →</Text>
                </TouchableOpacity>
              </>
            ) : (
              <View style={styles.reviewBox}>
                <Badge label="Not saved yet" variant="notSaved" />
                <Text style={[styles.reviewAmount, { color: colors.jamaGreen }]}>
                  - ₹{parseFloat(jamaAmountInput).toFixed(2)}
                </Text>
                <Text style={styles.reviewCustomer}>Repayment from {selectedCustomer?.name}</Text>
                <Text style={styles.reviewNewDue}>
                  New Balance Due: ₹
                  {Math.max(
                    0,
                    ((selectedCustomer?.amountDuePaise || 0) - Math.round(parseFloat(jamaAmountInput) * 100)) / 100
                  ).toFixed(2)}
                </Text>

                <View style={styles.modalActionButtonsRow}>
                  <TouchableOpacity
                    style={styles.modalBackBtn}
                    onPress={() => setJamaReviewing(false)}
                  >
                    <Text style={styles.modalBackBtnText}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.modalConfirmBtn, { backgroundColor: colors.success }]}
                    onPress={handleConfirmJama}
                  >
                    <Text style={styles.modalConfirmBtnText}>Confirm Jama</Text>
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
  listScroll: {
    flex: 1,
  },
  listContent: {
    padding: spacing.screenPadding,
    paddingBottom: 40,
  },
  detailScroll: {
    flex: 1,
  },
  detailContent: {
    padding: spacing.screenPadding,
    paddingBottom: 40,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  backButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.navy,
  },
  totalKhataCard: {
    marginBottom: 14,
  },
  khataHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  khataTotalLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.textSecondary,
    letterSpacing: 0.3,
  },
  khataTotalAmount: {
    fontSize: 26,
    fontWeight: '900',
    color: colors.udhaarRed,
    marginTop: 2,
  },
  khataCountSub: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 4,
  },
  addCustomerTopBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    gap: 5,
    borderWidth: 1,
    borderColor: '#CCE7F6',
  },
  addCustomerTopBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.navy,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radii.input,
    paddingHorizontal: 12,
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 16,
  },
  searchInput: {
    flex: 1,
    marginLeft: 8,
    fontSize: 13,
    color: colors.textMain,
  },
  listSectionTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.navy,
    marginBottom: 10,
  },
  customerRowCard: {
    marginBottom: 8,
    padding: 12,
  },
  customerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatarCircle: {
    width: 44,
    height: 44,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#CCE7F6',
  },
  avatarInitial: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.navy,
  },
  customerName: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.textMain,
  },
  customerPhone: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  customerLastActive: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 2,
  },
  customerDueLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  customerDueAmount: {
    fontSize: 15,
    fontWeight: '800',
    marginTop: 1,
  },
  customerProfileCard: {
    marginBottom: 16,
  },
  profileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  profileAvatarLarge: {
    width: 56,
    height: 56,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.primaryCyan,
  },
  profileAvatarLargeText: {
    fontSize: 24,
    fontWeight: '900',
    color: colors.navy,
  },
  customerDetailName: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.navy,
  },
  customerDetailPhone: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  aliasRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    marginTop: 4,
    gap: 4,
  },
  aliasLabel: {
    fontSize: 11,
    color: colors.textMuted,
  },
  aliasPill: {
    fontSize: 10,
    backgroundColor: colors.surfaceSubtle,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radii.pill,
    color: colors.textSecondary,
    borderWidth: 1,
    borderColor: colors.border,
  },
  balanceBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 14,
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  balanceBoxLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  balanceBoxAmount: {
    fontSize: 28,
    fontWeight: '900',
    marginVertical: 4,
  },
  balanceBoxSub: {
    fontSize: 10,
    color: colors.textMuted,
  },
  customerActionRow: {
    flexDirection: 'row',
    gap: 10,
  },
  primaryCustomerBtn: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: radii.button,
    borderWidth: 1,
    gap: 6,
  },
  primaryCustomerBtnText: {
    fontSize: 13,
    fontWeight: '800',
  },
  reminderLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
    gap: 6,
  },
  reminderLinkText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#166534',
  },
  ledgerSectionTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.navy,
    marginBottom: 10,
  },
  ledgerHistoryCard: {
    padding: 12,
  },
  ledgerEntryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
  },
  entryTypeIndicator: {
    width: 32,
    height: 32,
    borderRadius: radii.circle,
    justifyContent: 'center',
    alignItems: 'center',
  },
  entrySummary: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textMain,
  },
  entryTimestamp: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  ledgerDivider: {
    height: 1,
    backgroundColor: colors.borderSubtle,
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
  modalSheetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  modalSheetTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.navy,
  },
  modalSheetSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 16,
    lineHeight: 16,
  },
  modalCustomerBanner: {
    backgroundColor: colors.paleBlue,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginBottom: 14,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalCustomerBannerName: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.navy,
  },
  modalCustomerBannerDue: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 6,
  },
  modalTextInput: {
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.input,
    paddingHorizontal: 12,
    fontSize: 14,
    color: colors.textMain,
    marginBottom: 14,
  },
  amountInputBig: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.navy,
    height: 52,
  },
  submitModalBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
    marginTop: 6,
  },
  submitModalBtnText: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textWhite,
  },
  reviewBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.card,
    padding: 16,
    alignItems: 'center',
    marginBottom: 10,
  },
  reviewAmount: {
    fontSize: 28,
    fontWeight: '900',
    color: colors.udhaarRed,
    marginVertical: 8,
  },
  reviewCustomer: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textMain,
  },
  reviewNewDue: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: 16,
  },
  modalActionButtonsRow: {
    flexDirection: 'row',
    gap: 10,
    width: '100%',
  },
  modalBackBtn: {
    flex: 1,
    backgroundColor: '#F1F5F9',
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  modalBackBtnText: {
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
  errorAlertBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.errorSurface,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginBottom: 12,
    gap: 6,
  },
  errorAlertText: {
    fontSize: 12,
    color: colors.error,
    fontWeight: '600',
    flex: 1,
  },
});
