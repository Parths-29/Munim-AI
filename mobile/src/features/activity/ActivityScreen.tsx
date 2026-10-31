import React, { useState } from 'react';
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
import { Badge } from '@/components/common/Badge';
import { useDemoData } from '@/context/DemoDataContext';
import { TimelineEvent } from '@/api/ledgerClient';

type ActivityFilter = 'ALL' | 'KHATA' | 'PAYMENTS' | 'STOCK' | 'ACTIONS';

interface ActivityScreenProps {
  onBack?: () => void;
}

export const ActivityScreen: React.FC<ActivityScreenProps> = ({ onBack }) => {
  const { activityEvents } = useDemoData();
  const [activeFilter, setActiveFilter] = useState<ActivityFilter>('ALL');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const filteredEvents = activityEvents.filter((e) => {
    if (activeFilter === 'ALL') return true;
    if (activeFilter === 'KHATA') return e.event_type.includes('CREDIT') || e.event_type.includes('JAMA') || e.event_type.includes('CUSTOMER');
    if (activeFilter === 'PAYMENTS') return e.event_type.includes('PAYMENT');
    if (activeFilter === 'STOCK') return e.event_type.includes('STOCK');
    if (activeFilter === 'ACTIONS') return e.event_type.includes('ACTION') || e.event_type.includes('REMINDER');
    return true;
  });

  const toggleExpand = (id: string) => {
    setExpandedEventId(expandedEventId === id ? null : id);
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

        <View style={styles.header}>
          <Text style={styles.heading}>Audit & Activity History</Text>
          <Text style={styles.subheading}>Append-only business memory stream</Text>
        </View>

        {/* Filter Pills */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow}>
          {(['ALL', 'KHATA', 'PAYMENTS', 'STOCK', 'ACTIONS'] as ActivityFilter[]).map((f) => (
            <TouchableOpacity
              key={f}
              style={[styles.filterPill, activeFilter === f && styles.filterPillActive]}
              onPress={() => setActiveFilter(f)}
            >
              <Text style={[styles.filterPillText, activeFilter === f && styles.filterPillTextActive]}>
                {f}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Activity Items List */}
        <PaytmCard style={styles.eventsCard}>
          {filteredEvents.map((evt, idx) => {
            const isExpanded = expandedEventId === evt.event_id;
            return (
              <View key={evt.event_id || idx}>
                <TouchableOpacity
                  style={styles.eventRow}
                  onPress={() => toggleExpand(evt.event_id)}
                  activeOpacity={0.7}
                >
                  <View style={styles.iconCircle}>
                    <Ionicons
                      name={
                        evt.event_type.includes('CREDIT')
                          ? 'add'
                          : evt.event_type.includes('JAMA')
                          ? 'arrow-down'
                          : evt.event_type.includes('PAYMENT')
                          ? 'card'
                          : evt.event_type.includes('STOCK')
                          ? 'cube'
                          : 'sparkles'
                      }
                      size={16}
                      color={colors.navy}
                    />
                  </View>

                  <View style={{ flex: 1, marginHorizontal: 10 }}>
                    <Text style={styles.eventSummary}>{evt.summary}</Text>
                    <Text style={styles.eventTimestamp}>
                      {new Date(evt.created_at).toLocaleString([], {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })} · {evt.source_channel}
                    </Text>
                  </View>

                  <Badge
                    label={evt.status}
                    variant={evt.status === 'CONFIRMED' ? 'success' : 'neutral'}
                  />
                </TouchableOpacity>

                {/* Expandable Technical Details */}
                {isExpanded && (
                  <View style={styles.expandedBox}>
                    <Text style={styles.expandedLabel}>Technical Audit Detail:</Text>
                    <Text style={styles.expandedText}>• Event ID: {evt.event_id}</Text>
                    <Text style={styles.expandedText}>• Type: {evt.event_type}</Text>
                    <Text style={styles.expandedText}>• Source: {evt.source_channel}</Text>
                    <Text style={styles.expandedText}>• Status: {evt.status}</Text>
                  </View>
                )}

                {idx < filteredEvents.length - 1 && <View style={styles.divider} />}
              </View>
            );
          })}
        </PaytmCard>
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
  header: { marginBottom: 12 },
  heading: { fontSize: 18, fontWeight: '900', color: colors.navy },
  subheading: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  filterRow: { flexDirection: 'row', marginBottom: 14 },
  filterPill: {
    backgroundColor: colors.surface,
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: 8,
  },
  filterPillActive: {
    backgroundColor: colors.paleBlue,
    borderColor: colors.primaryCyan,
  },
  filterPillText: { fontSize: 11, fontWeight: '700', color: colors.textSecondary },
  filterPillTextActive: { color: colors.navy, fontWeight: '800' },
  eventsCard: { padding: 12 },
  eventRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
  iconCircle: {
    width: 34,
    height: 34,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  eventSummary: { fontSize: 13, fontWeight: '700', color: colors.textMain, lineHeight: 18 },
  eventTimestamp: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  expandedBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginVertical: 6,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  expandedLabel: { fontSize: 11, fontWeight: '800', color: colors.navy, marginBottom: 4 },
  expandedText: { fontSize: 11, color: colors.textSecondary, lineHeight: 16 },
  divider: { height: 1, backgroundColor: colors.borderSubtle },
});
