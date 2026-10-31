import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { Badge } from '@/components/common/Badge';
import { useDemoData } from '@/context/DemoDataContext';

interface MoreScreenProps {
  onNavigateTo: (screen: 'payment_review' | 'suppliers' | 'scan_bill' | 'bahi_khata' | 'reminders' | 'insights' | 'activity') => void;
}

export const MoreScreen: React.FC<MoreScreenProps> = ({ onNavigateTo }) => {
  const { pendingReviewCount, resetToDefaultFixture } = useDemoData();

  const handleResetFixture = () => {
    Alert.alert(
      'Reset Demo Fixture',
      'Reset all customer balances, inventory counts, and payments back to the clean starting demo fixture (Raju ₹500, Maggi 12 packs)?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset to Clean State',
          style: 'destructive',
          onPress: () => {
            resetToDefaultFixture();
            Alert.alert('Fixture Reset', 'Demo state restored to starting values.');
          },
        },
      ]
    );
  };

  const MENU_ITEMS = [
    {
      id: 'payment_review' as const,
      title: 'Payment Review Queue',
      subtitle: 'Reconcile unmatched UPI payments to customers',
      icon: 'card-outline' as const,
      badge: pendingReviewCount > 0 ? `${pendingReviewCount} Needs Review` : undefined,
      badgeVariant: 'warning' as const,
    },
    {
      id: 'suppliers' as const,
      title: 'Supplier Khata',
      subtitle: 'Wholesale vendor payables and payments',
      icon: 'business-outline' as const,
    },
    {
      id: 'scan_bill' as const,
      title: 'Scan Supplier Bill',
      subtitle: 'Inward stock OCR and delivery draft',
      icon: 'receipt-outline' as const,
    },
    {
      id: 'bahi_khata' as const,
      title: 'Scan Handwritten Bahi-Khata',
      subtitle: 'Digitize physical diary ledger entries',
      icon: 'book-outline' as const,
    },
    {
      id: 'reminders' as const,
      title: 'Overdue Reminders',
      subtitle: 'Consent-aware collection drafts and outbox',
      icon: 'logo-whatsapp' as const,
    },
    {
      id: 'insights' as const,
      title: 'Business Insights & Growth',
      subtitle: 'Report cards, metric trends, mock actions',
      icon: 'bar-chart-outline' as const,
    },
    {
      id: 'activity' as const,
      title: 'Activity & Audit Trail',
      subtitle: 'Full append-only event stream and IDs',
      icon: 'time-outline' as const,
    },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.heading}>More Features</Text>
        <Text style={styles.subheading}>KiranaOS Shop Services & Configurations</Text>
      </View>

      {/* Services Grid / List */}
      <PaytmCard style={styles.menuCard}>
        {MENU_ITEMS.map((item, index) => (
          <View key={item.id}>
            <TouchableOpacity
              style={styles.menuRow}
              onPress={() => onNavigateTo(item.id)}
              activeOpacity={0.7}
            >
              <View style={styles.iconCircle}>
                <Ionicons name={item.icon} size={22} color={colors.navy} />
              </View>

              <View style={{ flex: 1, marginHorizontal: 12 }}>
                <View style={styles.titleRow}>
                  <Text style={styles.itemTitle}>{item.title}</Text>
                  {item.badge && <Badge label={item.badge} variant={item.badgeVariant || 'neutral'} />}
                </View>
                <Text style={styles.itemSub}>{item.subtitle}</Text>
              </View>

              <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
            </TouchableOpacity>
            {index < MENU_ITEMS.length - 1 && <View style={styles.divider} />}
          </View>
        ))}
      </PaytmCard>

      {/* Demo Controls & Settings Card */}
      <Text style={styles.sectionHeading}>Demo Controls & Test Tools</Text>
      <PaytmCard style={styles.demoCard}>
        <View style={styles.demoHeader}>
          <Ionicons name="construct-outline" size={20} color={colors.navy} />
          <Text style={styles.demoTitle}>Hackathon Fixture Reset</Text>
        </View>
        <Text style={styles.demoDesc}>
          Restores starting state: Raju bhai due at ₹500, Maggi at 12 packs, 1 unmatched payment.
        </Text>

        <TouchableOpacity style={styles.resetBtn} onPress={handleResetFixture}>
          <Ionicons name="refresh" size={16} color={colors.udhaarRed} />
          <Text style={styles.resetBtnText}>Reset to Default Demo Fixture</Text>
        </TouchableOpacity>
      </PaytmCard>

      {/* Hackathon Disclaimer */}
      <View style={styles.disclaimerBox}>
        <Text style={styles.disclaimerTitle}>Paytm Build for India AI Hackathon Demo</Text>
        <Text style={styles.disclaimerText}>
          Track 1: Merchant Growth AI. All customer credit, payments, and stock movements are synthetic and recorded via KiranaOS structured shop memory layer. No live Paytm systems connected.
        </Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.screenPadding, paddingBottom: 40 },
  header: { marginBottom: 14 },
  heading: { fontSize: 20, fontWeight: '900', color: colors.navy },
  subheading: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  menuCard: { padding: 8, marginBottom: 20 },
  menuRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 6 },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  itemTitle: { fontSize: 14, fontWeight: '800', color: colors.textMain },
  itemSub: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  divider: { height: 1, backgroundColor: colors.borderSubtle },
  sectionHeading: { fontSize: 14, fontWeight: '800', color: colors.navy, marginBottom: 10 },
  demoCard: { padding: 14, marginBottom: 16 },
  demoHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  demoTitle: { fontSize: 14, fontWeight: '800', color: colors.navy },
  demoDesc: { fontSize: 12, color: colors.textSecondary, lineHeight: 16, marginBottom: 12 },
  resetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.errorSurface,
    paddingVertical: 10,
    borderRadius: radii.button,
    borderWidth: 1,
    borderColor: '#FECACA',
    gap: 6,
  },
  resetBtnText: { fontSize: 12, fontWeight: '800', color: colors.udhaarRed },
  disclaimerBox: { alignItems: 'center', paddingVertical: 10 },
  disclaimerTitle: { fontSize: 11, fontWeight: '800', color: colors.textSecondary },
  disclaimerText: { fontSize: 10, color: colors.textMuted, textAlign: 'center', marginTop: 4, lineHeight: 14 },
});

