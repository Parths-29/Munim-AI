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
import { fetchEvents, TimelineEvent } from '@/api/ledgerClient';
import { SyntheticDataPill } from '@/components/InfoBanner';

export default function TimelineScreen() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEvents(50);
      setEvents(data);
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
