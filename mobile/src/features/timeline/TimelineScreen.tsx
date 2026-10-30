import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fetchActivitySummary, fetchEvents, ActivitySummaryResponse, TimelineEvent } from '@/api/ledgerClient';
import { SyntheticDataPill } from '@/components/InfoBanner';

export default function TimelineScreen() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [summary, setSummary] = useState<ActivitySummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEvents(50);
      setEvents(data);
      const activitySummary = await fetchActivitySummary().catch(() => null);
      setSummary(activitySummary);
      if (!activitySummary) setError('Detailed summary is unavailable right now; the event list is still available below.');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Failed to load timeline events: ${message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const getStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case 'POSTED':
      case 'CONFIRMED':
      case 'SUCCESS':
        return '#28a745';
      case 'OBSERVED':
      case 'REVIEW':
        return '#ffc107';
      case 'FAILED':
      case 'REJECTED':
        return '#dc3545';
      default:
        return '#0f3460';
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <SyntheticDataPill />

      <View style={styles.header}>
        <Text style={styles.title}>Activity Timeline</Text>
        <TouchableOpacity style={styles.refreshBtn} onPress={loadEvents} disabled={loading}>
          <Ionicons name="refresh" size={18} color="#0f3460" />
          <Text style={styles.refreshText}>Refresh</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.subtitle}>
        Append-only business memory stream. Audit trail for credit, repayment, counts, and mock payments.
      </Text>

      {summary && (
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Shop Activity Summary</Text>
          <Text style={styles.summaryPeriod}>{summary.period_label}</Text>
          <Text style={styles.summaryDescription}>{summary.summary_text}</Text>
          <View style={styles.summaryGrid}>
            <Text style={styles.summaryMetric}>Credits: {summary.credit_entry_count} · ₹{(summary.credit_total_paise / 100).toFixed(2)}</Text>
            <Text style={styles.summaryMetric}>Repayments: {summary.repayment_entry_count} · ₹{(summary.repayment_total_paise / 100).toFixed(2)}</Text>
            <Text style={styles.summaryMetric}>Successful mock payments: {summary.successful_payment_count} · ₹{(summary.successful_payment_total_paise / 100).toFixed(2)}</Text>
            <Text style={styles.summaryMetric}>Waiting for review: {summary.open_review_payment_count} · ₹{(summary.open_review_payment_total_paise / 100).toFixed(2)}</Text>
            <Text style={styles.summaryMetric}>Pending / failed / reversed: {summary.pending_payment_count} / {summary.failed_payment_count} / {summary.reversed_payment_count}</Text>
            <Text style={styles.summaryMetric}>Stockout notes / physical counts: {summary.stockout_observation_count} / {summary.physical_count_event_count}</Text>
            <Text style={styles.summaryMetric}>Recorded events: {summary.recorded_event_count}</Text>
          </View>
          {summary.recent_payments.length > 0 && (
            <View style={styles.recentPayments}>
              <Text style={styles.recentPaymentsTitle}>Latest mock payment events</Text>
              {summary.recent_payments.map((payment) => (
                <Text key={payment.event_id} style={styles.recentPaymentLine}>
                  {payment.payment_status} · ₹{(payment.amount_paise / 100).toFixed(2)} · {payment.resolution_status}{payment.reason ? ` (${payment.reason.replace(/_/g, ' ')})` : ''}
                </Text>
              ))}
            </View>
          )}
          {summary.caveats.map((caveat, index) => (
            <Text key={index} style={styles.summaryCaveat}>• {caveat}</Text>
          ))}
        </View>
      )}

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading && <ActivityIndicator size="small" color="#0f3460" style={{ marginVertical: 16 }} />}

      {!loading && events.length === 0 && (
        <View style={styles.emptyCard}>
          <Ionicons name="time-outline" size={32} color="#6c757d" />
          <Text style={styles.emptyTitle}>No Timeline Events</Text>
          <Text style={styles.emptySubtitle}>Events will appear here as ledger, stock, or payment actions occur.</Text>
        </View>
      )}

      {events.map((evt) => {
        const statusColor = getStatusColor(evt.status);
        return (
          <View key={evt.event_id} style={[styles.eventCard, { borderLeftColor: statusColor }]}>
            <View style={styles.eventHeader}>
              <Text style={styles.eventType}>{evt.event_type.replace(/_/g, ' ')}</Text>
              <View style={[styles.statusBadge, { backgroundColor: `${statusColor}22` }]}>
                <Text style={[styles.statusText, { color: statusColor }]}>{evt.status}</Text>
              </View>
            </View>

            <Text style={styles.summaryText}>{evt.summary}</Text>

            {evt.source_utterance && (
              <View style={styles.utteranceBox}>
                <Ionicons name="chatbubble-ellipses-outline" size={14} color="#6c757d" style={{ marginRight: 6 }} />
                <Text style={styles.utteranceText}>"{evt.source_utterance}"</Text>
              </View>
            )}

            <View style={styles.metaRow}>
              <Text style={styles.metaTime}>
                {new Date(evt.created_at).toLocaleTimeString('en-IN', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </Text>
              <Text style={styles.eventIdText}>ID: {evt.event_id}</Text>
            </View>
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8f9fa' },
  content: { padding: 16, paddingBottom: 32 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  title: { fontSize: 20, fontWeight: '700', color: '#0f3460' },
  refreshBtn: { flexDirection: 'row', alignItems: 'center', padding: 6 },
  refreshText: { marginLeft: 4, color: '#0f3460', fontWeight: '600', fontSize: 13 },
  subtitle: { fontSize: 13, color: '#6c757d', marginBottom: 14 },
  summaryCard: { backgroundColor: '#e8f4fd', borderWidth: 1, borderColor: '#b6d4fe', borderRadius: 8, padding: 12, marginBottom: 14 },
  summaryTitle: { color: '#0f3460', fontSize: 15, fontWeight: '800', marginBottom: 3 },
  summaryPeriod: { color: '#6c757d', fontSize: 10, marginBottom: 7 },
  summaryDescription: { color: '#212529', fontSize: 12, lineHeight: 17, marginBottom: 7 },
  summaryGrid: { gap: 4, marginBottom: 7 },
  summaryMetric: { color: '#34495e', fontSize: 11, lineHeight: 15 },
  recentPayments: { borderTopWidth: 1, borderTopColor: '#b6d4fe', paddingTop: 7, marginBottom: 5 },
  recentPaymentsTitle: { color: '#0f3460', fontSize: 11, fontWeight: '700', marginBottom: 3 },
  recentPaymentLine: { color: '#34495e', fontSize: 10, lineHeight: 14 },
  summaryCaveat: { color: '#856404', fontSize: 10, lineHeight: 14, marginTop: 2 },
  errorBanner: {
    backgroundColor: '#f8d7da',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#f5c6cb',
  },
  errorText: { color: '#721c24', fontSize: 13 },
  emptyCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 24,
    alignItems: 'center',
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#e9ecef',
  },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: '#495057', marginTop: 8 },
  emptySubtitle: { fontSize: 13, color: '#6c757d', textAlign: 'center', marginTop: 4 },
  eventCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: '#dee2e6',
    elevation: 1,
  },
  eventHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  eventType: { fontSize: 13, fontWeight: '700', color: '#0f3460', textTransform: 'uppercase' },
  statusBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  statusText: { fontSize: 11, fontWeight: '700' },
  summaryText: { fontSize: 14, color: '#212529', marginBottom: 6 },
  utteranceBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f1f3f5',
    padding: 6,
    borderRadius: 4,
    marginBottom: 6,
  },
  utteranceText: { fontSize: 12, color: '#495057', fontStyle: 'italic', flex: 1 },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 2,
  },
  metaTime: { fontSize: 11, color: '#adb5bd' },
  eventIdText: { fontSize: 10, color: '#adb5bd', fontFamily: 'monospace' },
});
