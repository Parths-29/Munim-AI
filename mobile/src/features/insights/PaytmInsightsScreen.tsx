import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { Badge } from '@/components/common/Badge';
import { useDemoData } from '@/context/DemoDataContext';
import { ShopPersona } from '@/components/common/PaytmHeader';

interface PaytmInsightsScreenProps {
  onBack?: () => void;
}

export const PaytmInsightsScreen: React.FC<PaytmInsightsScreenProps> = ({ onBack }) => {
  const {
    persona,
    setPersona,
    facts,
    loadingFacts,
    approvedGrowthAction,
    approveGrowthAction,
  } = useDemoData();

  const [evidenceDrawerOpen, setEvidenceDrawerOpen] = useState(false);
  const [actionText, setActionText] = useState(
    'Counter Notice: ₹10 Cash Discount on UPI payments above ₹200'
  );
  const [approving, setApproving] = useState(false);

  const handleApproveAction = async () => {
    setApproving(true);
    await approveGrowthAction(actionText);
    setApproving(false);
    Alert.alert(
      'Growth Action Approved (Demo)',
      'Scheduled a 7-day observation tracking window. As this is a simulation, no live public marketing or notices were posted.'
    );
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

        {/* Top Header Card */}
        <PaytmCard variant="paleBlue" style={styles.headerCard}>
          <View style={styles.headerRow}>
            <View>
              <Text style={styles.headerLabel}>BUSINESS REPORTING BRIEF</Text>
              <Text style={styles.headerTitle}>Performance & Insights</Text>
              <Text style={styles.windowSub}>
                Window: {facts?.period ? `${facts.period.start} to ${facts.period.end}` : '90-Day Synthetic Fixture'}
              </Text>
            </View>
            <Badge label="Evidence Grounded" variant="demo" />
          </View>
        </PaytmCard>

        {/* Persona Selector Tabs */}
        <View style={styles.personaTabs}>
          {(['kirana', 'tea_stall', 'medical_store'] as ShopPersona[]).map((p) => {
            const isSel = persona === p;
            return (
              <TouchableOpacity
                key={p}
                style={[styles.personaTab, isSel && styles.personaTabActive]}
                onPress={() => setPersona(p)}
              >
                <Text style={[styles.personaTabText, isSel && styles.personaTabTextActive]}>
                  {p === 'kirana' ? 'Kirana' : p === 'tea_stall' ? 'Tea Stall' : 'Pharmacy'}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {loadingFacts ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={colors.primaryCyan} />
            <Text style={styles.loadingText}>Computing deterministic business facts...</Text>
          </View>
        ) : (
          <>
            {/* ── METRIC TILES GRID ──────────────────────────────────── */}
            <View style={styles.kpiGrid}>
              {/* Metric 1: Collections */}
              <PaytmCard style={styles.kpiCard}>
                <Text style={styles.kpiTitle}>UPI Collections</Text>
                <Text style={styles.kpiAmount}>₹4,850</Text>
                <Text style={styles.kpiSub}>22 transactions</Text>
              </PaytmCard>

              {/* Metric 2: Median Payment */}
              <PaytmCard style={styles.kpiCard}>
                <Text style={styles.kpiTitle}>Median Payment</Text>
                <Text style={styles.kpiAmount}>₹150</Text>
                <Text style={styles.kpiSub}>Representative ticket size</Text>
              </PaytmCard>

              {/* Metric 3: Failure Rate */}
              <PaytmCard style={styles.kpiCard}>
                <Text style={styles.kpiTitle}>Failure Rate</Text>
                <Text style={[styles.kpiAmount, { color: colors.warning }]}>4.2%</Text>
                <Text style={styles.kpiSub}>Network / bank drops</Text>
              </PaytmCard>

              {/* Metric 4: Customer Dues */}
              <PaytmCard style={styles.kpiCard}>
                <Text style={styles.kpiTitle}>Total Udhaar Dues</Text>
                <Text style={[styles.kpiAmount, { color: colors.udhaarRed }]}>₹620.00</Text>
                <Text style={styles.kpiSub}>3 active debtors</Text>
              </PaytmCard>
            </View>

            {/* ── AI NARRATIVE & DETERMINISTIC SUMMARY ───────────────── */}
            <PaytmCard style={styles.summaryCard}>
              <View style={styles.summaryTitleRow}>
                <Ionicons name="sparkles" size={18} color={colors.primaryCyan} />
                <Text style={styles.summaryTitle}>Munim Business Synthesis</Text>
              </View>

              <Text style={styles.summaryText}>
                {facts?.caveats?.[0] ??
                  'Total UPI collection was ₹4,850 across 22 transactions. Payer token retention is stable, though 1 previously frequent payer was absent this window. Cashflow health remains resilient.'}
              </Text>

              {/* Toggle evidence drawer */}
              <TouchableOpacity
                style={styles.evidenceToggleBtn}
                onPress={() => setEvidenceDrawerOpen(!evidenceDrawerOpen)}
              >
                <Ionicons name="finger-print-outline" size={16} color={colors.navy} />
                <Text style={styles.evidenceToggleText}>
                  {evidenceDrawerOpen ? 'Hide Evidence & Definitions ▲' : 'Why am I seeing this? (Evidence IDs) ▼'}
                </Text>
              </TouchableOpacity>

              {evidenceDrawerOpen && (
                <View style={styles.evidenceDrawer}>
                  <Text style={styles.evidenceHeading}>Audit Evidence Mapping:</Text>
                  {facts?.evidence_ids && facts.evidence_ids.length > 0 ? (
                    facts.evidence_ids.map((id) => (
                      <Text key={id} style={styles.evidenceLine}>• Evidence ID: {id}</Text>
                    ))
                  ) : (
                    <>
                      <Text style={styles.evidenceLine}>• Volume Fact: EVT_SUM_VOL_90D (Confidence 1.0)</Text>
                      <Text style={styles.evidenceLine}>• Failure Fact: EVT_FAIL_UPI_RATE (Confidence 1.0)</Text>
                      <Text style={styles.evidenceLine}>• Absent Token: TOKEN_UPI_FREQ_889 (Observed zero count)</Text>
                    </>
                  )}
                  <Text style={styles.evidenceDisclaimer}>
                    *Deterministic facts layer strictly separates calculated facts from LLM text.
                  </Text>
                </View>
              )}
            </PaytmCard>

            {/* ── GROWTH ACTION FLOW ─────────────────────────────────── */}
            <PaytmCard style={styles.growthCard}>
              <View style={styles.growthHeader}>
                <Ionicons name="trending-up" size={20} color={colors.navy} />
                <Text style={styles.growthTitle}>Suggested Shop Growth Action</Text>
                <Badge label="Simulated" variant="simulated" />
              </View>

              <Text style={styles.growthSub}>
                Merchant-approved recommendation to re-engage absent customers:
              </Text>

              <TextInput
                style={styles.growthInput}
                value={actionText}
                onChangeText={setActionText}
                multiline
              />

              {!approvedGrowthAction ? (
                <TouchableOpacity
                  style={styles.approveActionBtn}
                  onPress={handleApproveAction}
                  disabled={approving}
                >
                  <Ionicons name="checkmark-circle" size={18} color={colors.textWhite} />
                  <Text style={styles.approveActionBtnText}>Approve & Track for 7 Days (Demo)</Text>
                </TouchableOpacity>
              ) : (
                <View style={styles.approvedBanner}>
                  <Ionicons name="checkmark-circle" size={20} color="#166534" />
                  <View style={{ flex: 1, marginLeft: 8 }}>
                    <Text style={styles.approvedTitle}>Approved Mock Action Active</Text>
                    <Text style={styles.approvedSub}>
                      Scheduled observation window active since {approvedGrowthAction.approvedAt}. Outcome metrics will compare pre/post lift without claiming causal certainty.
                    </Text>
                  </View>
                </View>
              )}
            </PaytmCard>
          </>
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
  headerCard: { marginBottom: 12 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  headerLabel: { fontSize: 10, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.3 },
  headerTitle: { fontSize: 18, fontWeight: '900', color: colors.navy, marginTop: 2 },
  windowSub: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  personaTabs: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    padding: 3,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  personaTab: {
    flex: 1,
    paddingVertical: 7,
    alignItems: 'center',
    borderRadius: radii.pill,
  },
  personaTabActive: {
    backgroundColor: colors.paleBlue,
  },
  personaTabText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  personaTabTextActive: {
    color: colors.navy,
    fontWeight: '800',
  },
  loadingBox: { alignItems: 'center', paddingVertical: 40 },
  loadingText: { fontSize: 13, color: colors.textSecondary, marginTop: 10 },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 14,
  },
  kpiCard: {
    width: '48%',
    padding: 12,
  },
  kpiTitle: { fontSize: 11, fontWeight: '700', color: colors.textSecondary },
  kpiAmount: { fontSize: 22, fontWeight: '900', color: colors.navy, marginVertical: 3 },
  kpiSub: { fontSize: 10, color: colors.textMuted },
  summaryCard: {
    marginBottom: 14,
    padding: 16,
  },
  summaryTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  summaryTitle: { fontSize: 15, fontWeight: '800', color: colors.navy },
  summaryText: { fontSize: 13, color: colors.textMain, lineHeight: 19, marginBottom: 12 },
  evidenceToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
  },
  evidenceToggleText: { fontSize: 12, fontWeight: '700', color: colors.navy },
  evidenceDrawer: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginTop: 10,
  },
  evidenceHeading: { fontSize: 11, fontWeight: '800', color: colors.navy, marginBottom: 4 },
  evidenceLine: { fontSize: 11, color: colors.textSecondary, lineHeight: 16 },
  evidenceDisclaimer: { fontSize: 10, color: colors.textMuted, fontStyle: 'italic', marginTop: 6 },
  growthCard: { padding: 16, marginBottom: 16 },
  growthHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  growthTitle: { fontSize: 15, fontWeight: '800', color: colors.navy, flex: 1 },
  growthSub: { fontSize: 12, color: colors.textSecondary, marginBottom: 10 },
  growthInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.input,
    padding: 12,
    fontSize: 13,
    color: colors.textMain,
    backgroundColor: colors.surfaceSubtle,
    minHeight: 64,
    marginBottom: 12,
  },
  approveActionBtn: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    gap: 8,
  },
  approveActionBtnText: { fontSize: 13, fontWeight: '800', color: colors.textWhite },
  approvedBanner: {
    flexDirection: 'row',
    backgroundColor: colors.successSurface,
    borderRadius: radii.cardSmall,
    padding: 12,
    borderWidth: 1,
    borderColor: '#B8DFBF',
  },
  approvedTitle: { fontSize: 13, fontWeight: '800', color: '#166534' },
  approvedSub: { fontSize: 11, color: '#166534', marginTop: 2, lineHeight: 15 },
});
