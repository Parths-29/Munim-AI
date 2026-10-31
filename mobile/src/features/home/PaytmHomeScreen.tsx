import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { ActionIcon } from '@/components/common/ActionIcon';
import { Badge } from '@/components/common/Badge';
import { useDemoData } from '@/context/DemoDataContext';

interface PaytmHomeScreenProps {
  onOpenMunim?: () => void;
  onOpenMunimVoice: () => void;
  onOpenMunimText: () => void;
  onNavigateTab: (tab: 'home' | 'khata' | 'stock' | 'more') => void;
  onOpenPaymentReview: () => void;
  onOpenScanBill: () => void;
  onOpenAddUdhaar: () => void;
  onOpenRecordJama: () => void;
  onOpenInsightsBrief: () => void;
  onOpenActivity: () => void;
  onOpenSearch: () => void;
}

export const PaytmHomeScreen: React.FC<PaytmHomeScreenProps> = ({
  onOpenMunim,
  onOpenMunimVoice,
  onOpenMunimText,
  onNavigateTab,
  onOpenPaymentReview,
  onOpenScanBill,
  onOpenAddUdhaar,
  onOpenRecordJama,
  onOpenInsightsBrief,
  onOpenActivity,
  onOpenSearch,
}) => {
  const {
    customers,
    products,
    pendingReviewCount,
    invoiceDrafts,
    activityEvents,
    facts,
  } = useDemoData();

  // Derived summaries
  const totalCustomerDuesPaise = customers.reduce((sum, c) => sum + c.amountDuePaise, 0);
  const lowStockCount = products.filter((p) => p.onHand <= p.reorderThreshold).length;
  const pendingInvoiceCount = invoiceDrafts.filter((d) => d.status === 'DRAFT').length;

  // Format currency helper
  const formatRupees = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  return (
    <ScrollView
      style={styles.scrollView}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
    >
      {/* ── B. Search / Quick Action Field ─────────────────────────────── */}
      <TouchableOpacity
        style={styles.searchBar}
        onPress={onOpenSearch}
        activeOpacity={0.8}
        accessibilityRole="search"
        accessibilityLabel="Search customers, products or actions"
      >
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <Text style={styles.searchPlaceholder}>Search customers, products or actions...</Text>
        <View style={styles.searchMicPill}>
          <Ionicons name="mic" size={14} color={colors.navy} />
        </View>
      </TouchableOpacity>

      {/* ── C. Summary Card (Strictly labeled) ─────────────────────────── */}
      <PaytmCard variant="elevated" style={styles.summaryCard}>
        <View style={styles.summaryHeader}>
          <View>
            <Text style={styles.summaryReportingPeriod}>SYNTHETIC REPORTING WINDOW (LAST 90 DAYS)</Text>
            <Text style={styles.summaryLabel}>Recorded UPI Collections</Text>
          </View>
          <Badge label="Simulated" variant="simulated" />
        </View>

        <View style={styles.collectionRow}>
          <Text style={styles.heroAmount}>₹4,850</Text>
          <Text style={styles.collectionTransactions}>22 transactions</Text>
        </View>

        <View style={styles.summaryDivider} />

        {/* Breakdown Row */}
        <View style={styles.metricsRow}>
          {/* Customer Dues */}
          <TouchableOpacity
            style={styles.metricCol}
            onPress={() => onNavigateTab('khata')}
            activeOpacity={0.7}
          >
            <Text style={styles.metricTitle}>Customer Dues</Text>
            <Text style={[styles.metricValue, { color: colors.udhaarRed }]}>
              {formatRupees(totalCustomerDuesPaise)}
            </Text>
            <Text style={styles.metricSub}>{customers.length} customers</Text>
          </TouchableOpacity>

          <View style={styles.metricBorder} />

          {/* Payments to Review */}
          <TouchableOpacity
            style={styles.metricCol}
            onPress={onOpenPaymentReview}
            activeOpacity={0.7}
          >
            <Text style={styles.metricTitle}>Payments to Review</Text>
            <Text style={[styles.metricValue, { color: pendingReviewCount > 0 ? colors.warning : colors.textMain }]}>
              {pendingReviewCount} Unmatched
            </Text>
            <Text style={styles.metricSub}>Needs allocation</Text>
          </TouchableOpacity>

          <View style={styles.metricBorder} />

          {/* Low Stock Items */}
          <TouchableOpacity
            style={styles.metricCol}
            onPress={() => onNavigateTab('stock')}
            activeOpacity={0.7}
          >
            <Text style={styles.metricTitle}>Low Stock Items</Text>
            <Text style={[styles.metricValue, { color: lowStockCount > 0 ? colors.warning : colors.success }]}>
              {lowStockCount} Items
            </Text>
            <Text style={styles.metricSub}>Below threshold</Text>
          </TouchableOpacity>
        </View>
      </PaytmCard>

      {/* ── D. Primary Action Tiles ───────────────────────────────── */}
      <View style={styles.primaryActionsRow}>
        <ActionIcon
          icon="sparkles"
          label="Munim AI"
          sublabel="Voice/Agent"
          variant="cyan"
          onPress={onOpenMunim ?? onOpenMunimVoice}
        />
        <ActionIcon
          icon="add-circle"
          label="Add Udhaar"
          sublabel="Credit"
          onPress={onOpenAddUdhaar}
        />
        <ActionIcon
          icon="arrow-down-circle"
          label="Record Jama"
          sublabel="Repayment"
          onPress={onOpenRecordJama}
        />
        <ActionIcon
          icon="shield-checkmark"
          label="Review Pay"
          sublabel="Reconcile"
          badgeCount={pendingReviewCount}
          onPress={onOpenPaymentReview}
        />
        <ActionIcon
          icon="receipt"
          label="Scan Bill"
          sublabel="Inward"
          onPress={onOpenScanBill}
        />
      </View>

      {/* ── E. Prominent Munim Copilot Card ────────────────────────────── */}
      <TouchableOpacity
        activeOpacity={0.92}
        onPress={onOpenMunim ?? onOpenMunimVoice}
        accessibilityRole="button"
        accessibilityLabel="Open Munim AI Assistant"
      >
        <PaytmCard variant="paleBlue" style={styles.copilotHeroCard}>
          <View style={styles.copilotContent}>
            <View style={{ flex: 1, paddingRight: 10 }}>
              <View style={styles.copilotTagRow}>
                <Ionicons name="sparkles" size={14} color={colors.deepCyan} />
                <Text style={styles.copilotTag}>MUNIM AI VOICE COPILOT</Text>
              </View>
              <Text style={styles.copilotHeading}>Boliye, Munim sun raha hai</Text>
              <Text style={styles.copilotSub}>
                Voice assistant, live ledger actions, credit & stock.
              </Text>

              <View style={styles.typeInsteadBtn}>
                <Ionicons name="mic-outline" size={14} color={colors.navy} />
                <Text style={styles.typeInsteadText}>Tap to talk or chat</Text>
              </View>
            </View>

            {/* Big Mic Button */}
            <View style={styles.largeMicButton}>
              <View style={styles.largeMicRing}>
                <Ionicons name="mic" size={32} color={colors.navy} />
              </View>
              <Text style={styles.tapToSpeak}>Bolo</Text>
            </View>
          </View>
        </PaytmCard>
      </TouchableOpacity>

      {/* ── F. "Needs your attention" ──────────────────────────────────── */}
      <View style={styles.sectionHeaderRow}>
        <Text style={styles.sectionHeading}>Needs your attention</Text>
        <Badge label="Action Required" variant="warning" />
      </View>

      {/* Attention Item 1: Payment Review */}
      {pendingReviewCount > 0 && (
        <PaytmCard style={styles.attentionCard}>
          <View style={styles.attentionRow}>
            <View style={[styles.attentionIconCircle, { backgroundColor: '#FFFBEB' }]}>
              <Ionicons name="card-outline" size={20} color={colors.warning} />
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <View style={styles.attentionTitleRow}>
                <Text style={styles.attentionTitle}>Unmatched ₹300.00 Payment</Text>
                <Badge label="Review" variant="warning" />
              </View>
              <Text style={styles.attentionDesc}>
                Mock UPI payment from Payer_UPI_9876 requires manual allocation.
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.attentionActionBtn}
            onPress={onOpenPaymentReview}
          >
            <Text style={styles.attentionActionBtnText}>Link to Customer Due →</Text>
          </TouchableOpacity>
        </PaytmCard>
      )}

      {/* Attention Item 2: Low Stock Warning */}
      {lowStockCount > 0 && (
        <PaytmCard style={styles.attentionCard}>
          <View style={styles.attentionRow}>
            <View style={[styles.attentionIconCircle, { backgroundColor: '#FDE8E9' }]}>
              <Ionicons name="cube-outline" size={20} color={colors.error} />
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <View style={styles.attentionTitleRow}>
                <Text style={styles.attentionTitle}>Stock Alert: Maggi Noodles</Text>
                <Badge label="Low Stock" variant="error" />
              </View>
              <Text style={styles.attentionDesc}>
                Current on-hand: 12 packs (Threshold: 15 packs).
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.attentionActionBtn}
            onPress={() => onNavigateTab('stock')}
          >
            <Text style={styles.attentionActionBtnText}>Check Stock & Reorder →</Text>
          </TouchableOpacity>
        </PaytmCard>
      )}

      {/* Attention Item 3: Invoice Draft */}
      {pendingInvoiceCount > 0 && (
        <PaytmCard style={styles.attentionCard}>
          <View style={styles.attentionRow}>
            <View style={[styles.attentionIconCircle, { backgroundColor: colors.paleBlue }]}>
              <Ionicons name="document-text-outline" size={20} color={colors.navy} />
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <View style={styles.attentionTitleRow}>
                <Text style={styles.attentionTitle}>Supplier Bill Draft Ready</Text>
                <Badge label="Draft" variant="draft" />
              </View>
              <Text style={styles.attentionDesc}>
                Krishna FMCG #INV-2026-904 (₹696.00) awaits stock inward confirmation.
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.attentionActionBtn}
            onPress={onOpenScanBill}
          >
            <Text style={styles.attentionActionBtnText}>Review & Confirm Inward →</Text>
          </TouchableOpacity>
        </PaytmCard>
      )}

      {/* ── G. Business Brief: "Aaj kaisa raha?" ──────────────────────── */}
      <PaytmCard style={styles.briefCard}>
        <View style={styles.briefHeader}>
          <View style={styles.sparkleRow}>
            <Ionicons name="bar-chart" size={18} color={colors.primaryCyan} />
            <Text style={styles.briefTitle}>Aaj kaisa raha?</Text>
          </View>
          <Badge label="Business Brief" variant="demo" />
        </View>

        <Text style={styles.briefText}>
          {facts?.caveats?.[0] ??
            'Recorded ₹4,850 in collections across 22 transactions. 1 repeat payer absent in current 90-day window. Customer dues stand at ₹620.'}
        </Text>

        <TouchableOpacity
          style={styles.briefCTAButton}
          onPress={onOpenInsightsBrief}
          activeOpacity={0.8}
        >
          <Text style={styles.briefCTAText}>View Business Brief & Growth Action →</Text>
        </TouchableOpacity>
      </PaytmCard>

      {/* ── H. Recent Activity Feed ───────────────────────────────────── */}
      <View style={styles.sectionHeaderRow}>
        <Text style={styles.sectionHeading}>Recent Activity</Text>
        <TouchableOpacity onPress={onOpenActivity}>
          <Text style={styles.viewAllText}>View all</Text>
        </TouchableOpacity>
      </View>

      <PaytmCard style={styles.activityCard}>
        {activityEvents.slice(0, 4).map((evt, idx) => (
          <View key={evt.event_id || idx}>
            <View style={styles.activityRow}>
              <View style={styles.activityDotCircle}>
                <Ionicons
                  name={
                    evt.event_type.includes('CREDIT')
                      ? 'add'
                      : evt.event_type.includes('JAMA')
                      ? 'checkmark'
                      : evt.event_type.includes('PAYMENT')
                      ? 'card'
                      : evt.event_type.includes('STOCK')
                      ? 'cube'
                      : 'information'
                  }
                  size={14}
                  color={colors.navy}
                />
              </View>
              <View style={styles.activityDetails}>
                <Text style={styles.activitySummary} numberOfLines={2}>
                  {evt.summary}
                </Text>
                <Text style={styles.activityTime}>
                  {new Date(evt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {evt.source_channel}
                </Text>
              </View>
              <Badge label={evt.status} variant={evt.status === 'CONFIRMED' ? 'success' : 'neutral'} />
            </View>
            {idx < Math.min(activityEvents.length, 4) - 1 && <View style={styles.activityDivider} />}
          </View>
        ))}
      </PaytmCard>

      <View style={{ height: 30 }} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  scrollView: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingHorizontal: spacing.screenPadding,
    paddingTop: 12,
    paddingBottom: 20,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radii.input,
    paddingHorizontal: 14,
    height: 46,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 14,
    ...shadows.subtle,
  },
  searchPlaceholder: {
    fontSize: 13,
    color: colors.textSecondary,
    marginLeft: 10,
    flex: 1,
  },
  searchMicPill: {
    width: 28,
    height: 28,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  summaryCard: {
    marginBottom: 16,
  },
  summaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  summaryReportingPeriod: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.textSecondary,
    letterSpacing: 0.3,
  },
  summaryLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.navy,
    marginTop: 2,
  },
  collectionRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 6,
    marginBottom: 12,
  },
  heroAmount: {
    fontSize: typography.fontSize.heroAmount,
    fontWeight: '900',
    color: colors.navy,
    letterSpacing: -0.5,
  },
  collectionTransactions: {
    fontSize: 13,
    color: colors.textSecondary,
    marginLeft: 10,
    fontWeight: '600',
  },
  summaryDivider: {
    height: 1,
    backgroundColor: colors.borderSubtle,
    marginVertical: 10,
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 4,
  },
  metricCol: {
    flex: 1,
    alignItems: 'center',
  },
  metricBorder: {
    width: 1,
    height: '80%',
    backgroundColor: colors.borderSubtle,
    alignSelf: 'center',
  },
  metricTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 3,
    textAlign: 'center',
  },
  metricValue: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.textMain,
  },
  metricSub: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 2,
  },
  primaryActionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 16,
    ...shadows.subtle,
  },
  copilotHeroCard: {
    marginBottom: 20,
    borderColor: '#BAE6FD',
  },
  copilotContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  copilotTagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  copilotTag: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.deepCyan,
    letterSpacing: 0.5,
  },
  copilotHeading: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.navy,
    lineHeight: 22,
  },
  copilotSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 3,
    lineHeight: 16,
  },
  typeInsteadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radii.pill,
    alignSelf: 'flex-start',
    marginTop: 10,
    gap: 5,
    borderWidth: 1,
    borderColor: '#CCE7F6',
  },
  typeInsteadText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.navy,
  },
  largeMicButton: {
    alignItems: 'center',
  },
  largeMicRing: {
    width: 64,
    height: 64,
    borderRadius: radii.circle,
    backgroundColor: colors.primaryCyan,
    justifyContent: 'center',
    alignItems: 'center',
    ...shadows.cyanGlow,
  },
  tapToSpeak: {
    fontSize: 11,
    fontWeight: '800',
    color: colors.navy,
    marginTop: 5,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    marginTop: 4,
  },
  sectionHeading: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.navy,
  },
  viewAllText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.primaryCyan,
  },
  attentionCard: {
    marginBottom: 10,
    padding: 12,
  },
  attentionRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  attentionIconCircle: {
    width: 38,
    height: 38,
    borderRadius: radii.circle,
    justifyContent: 'center',
    alignItems: 'center',
  },
  attentionTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  attentionTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textMain,
  },
  attentionDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 16,
  },
  attentionActionBtn: {
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
    alignItems: 'flex-end',
  },
  attentionActionBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.primaryCyan,
  },
  briefCard: {
    marginBottom: 20,
    borderLeftWidth: 4,
    borderLeftColor: colors.primaryCyan,
  },
  briefHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  sparkleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  briefTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.navy,
  },
  briefText: {
    fontSize: 13,
    color: colors.textMain,
    lineHeight: 19,
    marginBottom: 12,
  },
  briefCTAButton: {
    backgroundColor: colors.paleBlue,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radii.button,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  briefCTAText: {
    fontSize: 12,
    fontWeight: '800',
    color: colors.navy,
  },
  activityCard: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    marginBottom: 20,
  },
  activityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
  },
  activityDotCircle: {
    width: 28,
    height: 28,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  activityDetails: {
    flex: 1,
    marginRight: 8,
  },
  activitySummary: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textMain,
    lineHeight: 17,
  },
  activityTime: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  activityDivider: {
    height: 1,
    backgroundColor: colors.borderSubtle,
  },
});
