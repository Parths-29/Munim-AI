import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { Badge } from '@/components/common/Badge';
import { useDemoData, DemoReminder } from '@/context/DemoDataContext';

interface RemindersScreenProps {
  onBack?: () => void;
}

export const RemindersScreen: React.FC<RemindersScreenProps> = ({ onBack }) => {
  const { reminders, approveReminder, mockSendReminder } = useDemoData();
  const [selectedReminder, setSelectedReminder] = useState<DemoReminder | null>(reminders[0] || null);

  const handleApprove = (remId: string) => {
    approveReminder(remId);
    Alert.alert(
      'Reminder Approved (Simulated)',
      'Queued in the simulated outbox. In this prototype, no real WhatsApp or SMS messages are transmitted.'
    );
  };

  const handleSimulateDelivery = (remId: string) => {
    mockSendReminder(remId);
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

        {/* Disclaimer Banner */}
        <PaytmCard variant="paleBlue" style={styles.bannerCard}>
          <View style={styles.bannerRow}>
            <Ionicons name="shield-checkmark" size={20} color={colors.navy} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <View style={styles.badgeRow}>
                <Text style={styles.bannerTitle}>Consent-Aware Udhaar Reminders</Text>
                <Badge label="Simulated" variant="simulated" />
              </View>
              <Text style={styles.bannerDesc}>
                Reminders are generated only for overdue debts (15+ days) with explicit merchant consent. Prototype sends no real network messages.
              </Text>
            </View>
          </View>
        </PaytmCard>

        {/* Reminders List */}
        <Text style={styles.sectionHeading}>Awaiting Merchant Approval ({reminders.length})</Text>
        {reminders.map((rem) => (
          <PaytmCard key={rem.id} style={styles.reminderCard}>
            <View style={styles.cardHeader}>
              <View style={{ flex: 1 }}>
                <Text style={styles.custName}>{rem.customerName}</Text>
                <Text style={styles.custContact}>{rem.maskedPhone}</Text>
                <Text style={styles.overdueInfo}>
                  Overdue: ₹{(rem.overdueAmountPaise / 100).toFixed(2)} · {rem.daysOverdue} days old
                </Text>
              </View>
              <Badge
                label={
                  rem.status === 'AWAITING_APPROVAL'
                    ? 'Needs Approval'
                    : rem.status === 'MOCK_SENT'
                    ? 'Mock Sent'
                    : 'Mock Delivered'
                }
                variant={rem.status === 'AWAITING_APPROVAL' ? 'warning' : 'success'}
              />
            </View>

            {/* Consent Pill */}
            <View style={styles.consentPillRow}>
              <View style={styles.consentPill}>
                <Ionicons name="checkmark-circle" size={13} color="#166534" />
                <Text style={styles.consentText}>Opt-in Recorded: Verified Consent</Text>
              </View>
              <View style={styles.consentPill}>
                <Ionicons name="time" size={13} color={colors.navy} />
                <Text style={styles.consentText}>Timing: Safe Shop Hours</Text>
              </View>
            </View>

            {/* Message Preview Box */}
            <View style={styles.messageBox}>
              <Text style={styles.messageLabel}>Draft Message Preview (Hindi):</Text>
              <Text style={styles.messageBody}>{rem.messageText}</Text>
            </View>

            {/* Action Buttons */}
            <View style={styles.actionRow}>
              {rem.status === 'AWAITING_APPROVAL' && (
                <TouchableOpacity
                  style={styles.approveBtn}
                  onPress={() => handleApprove(rem.id)}
                >
                  <Ionicons name="checkmark" size={16} color={colors.textWhite} />
                  <Text style={styles.approveBtnText}>Approve Reminder</Text>
                </TouchableOpacity>
              )}

              {rem.status === 'MOCK_SENT' && (
                <TouchableOpacity
                  style={styles.simulateDeliveryBtn}
                  onPress={() => handleSimulateDelivery(rem.id)}
                >
                  <Ionicons name="paper-plane-outline" size={16} color={colors.navy} />
                  <Text style={styles.simulateDeliveryBtnText}>Simulate Mock Delivery</Text>
                </TouchableOpacity>
              )}

              {rem.status === 'MOCK_DELIVERED' && (
                <View style={styles.deliveredPill}>
                  <Ionicons name="checkmark-done" size={16} color="#166534" />
                  <Text style={styles.deliveredText}>Simulated Delivery Confirmed</Text>
                </View>
              )}
            </View>
          </PaytmCard>
        ))}
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
  bannerCard: { marginBottom: 14 },
  bannerRow: { flexDirection: 'row', alignItems: 'flex-start' },
  badgeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  bannerTitle: { fontSize: 13, fontWeight: '800', color: colors.navy },
  bannerDesc: { fontSize: 11, color: colors.textSecondary, lineHeight: 16 },
  sectionHeading: { fontSize: 14, fontWeight: '800', color: colors.navy, marginBottom: 10 },
  reminderCard: { marginBottom: 12, padding: 14 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  custName: { fontSize: 15, fontWeight: '800', color: colors.textMain },
  custContact: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  overdueInfo: { fontSize: 12, fontWeight: '700', color: colors.udhaarRed, marginTop: 3 },
  consentPillRow: { flexDirection: 'row', gap: 6, marginVertical: 10, flexWrap: 'wrap' },
  consentPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceSubtle,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    gap: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  consentText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  messageBox: {
    backgroundColor: '#F8FAFC',
    borderRadius: radii.cardSmall,
    padding: 10,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    marginBottom: 12,
  },
  messageLabel: { fontSize: 10, fontWeight: '700', color: colors.textSecondary, marginBottom: 4 },
  messageBody: { fontSize: 12, color: colors.textMain, lineHeight: 17 },
  actionRow: { flexDirection: 'row', justifyContent: 'flex-end' },
  approveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.navy,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: radii.button,
    gap: 6,
  },
  approveBtnText: { fontSize: 12, fontWeight: '800', color: colors.textWhite },
  simulateDeliveryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.paleBlue,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: radii.button,
    gap: 6,
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  simulateDeliveryBtnText: { fontSize: 12, fontWeight: '800', color: colors.navy },
  deliveredPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.successSurface,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: radii.pill,
    gap: 6,
  },
  deliveredText: { fontSize: 11, fontWeight: '700', color: '#166534' },
});

