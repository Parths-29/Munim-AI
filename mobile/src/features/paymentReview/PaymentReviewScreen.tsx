import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  fetchPaymentReviewQueue,
  allocatePaymentManually,
  PaymentReviewItem,
} from '@/api/ledgerClient';
import { SyntheticDataPill } from '@/components/InfoBanner';

export default function PaymentReviewScreen() {
  const [items, setItems] = useState<PaymentReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Allocation modal/form state
  const [selectedEvent, setSelectedEvent] = useState<PaymentReviewItem | null>(null);
  const [targetCustomerId, setTargetCustomerId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadReviewQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const queue = await fetchPaymentReviewQueue();
      setItems(queue);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Failed to load review queue: ${message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReviewQueue();
  }, [loadReviewQueue]);

  const handleManualAllocate = async () => {
    if (!selectedEvent) return;
    if (!targetCustomerId.trim()) {
      Alert.alert('Customer Required', 'Please enter a target Customer ID to allocate this payment.');
      return;
    }
    if (!confirmed) {
      Alert.alert(
        'Confirmation Required',
        'Merchant confirmation is required. Please check the confirmation box before manual allocation.'
      );
      return;
    }

    setSubmitting(true);
    setActionMessage(null);
    try {
      const res = await allocatePaymentManually(selectedEvent.event_id, {
        customer_id: targetCustomerId.trim(),
        confirmed: true,
        idempotency_key: `alloc_${selectedEvent.event_id}_${Date.now()}`,
      });
      setActionMessage(
        `✓ Payment ₹${(res.amount_paise / 100).toFixed(2)} allocated to customer ${res.customer_id}! Allocation Entry: ${res.allocation_entry_id}`
      );
      setSelectedEvent(null);
      setTargetCustomerId('');
      setConfirmed(false);
      loadReviewQueue();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      Alert.alert('Allocation Failed', message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <SyntheticDataPill />

      <View style={styles.header}>
        <Text style={styles.title}>Payment Review Queue</Text>
        <TouchableOpacity style={styles.refreshBtn} onPress={loadReviewQueue} disabled={loading}>
          <Ionicons name="refresh" size={18} color="#0f3460" />
          <Text style={styles.refreshText}>Refresh</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.disclaimerBox}>
        <Ionicons name="shield-checkmark-outline" size={16} color="#0f3460" style={{ marginRight: 6 }} />
        <Text style={styles.disclaimerText}>
          Mock UPI payments only. No connection to Paytm production servers.
          Unresolved payments require explicit merchant verification before allocation.
        </Text>
      </View>

      {actionMessage && (
        <View style={styles.successBanner}>
          <Text style={styles.successText}>{actionMessage}</Text>
        </View>
      )}

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading && <ActivityIndicator size="small" color="#0f3460" style={{ marginVertical: 16 }} />}

      {!loading && items.length === 0 && (
        <View style={styles.emptyCard}>
          <Ionicons name="checkmark-circle-outline" size={32} color="#28a745" />
          <Text style={styles.emptyTitle}>Review Queue Clear</Text>
          <Text style={styles.emptySubtitle}>No unallocated or ambiguous payments pending review.</Text>
        </View>
      )}

      {items.map((item) => (
        <View key={item.event_id} style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.eventAmount}>₹{(item.amount_paise / 100).toFixed(2)}</Text>
            <View style={styles.statusBadge}>
              <Text style={styles.statusBadgeText}>{item.status}</Text>
            </View>
          </View>

          <Text style={styles.detailRow}>
            <Text style={styles.detailLabel}>Event ID: </Text>
            <Text style={styles.detailValue}>{item.event_id}</Text>
          </Text>

          <Text style={styles.detailRow}>
            <Text style={styles.detailLabel}>Payer Token: </Text>
            <Text style={styles.detailValue}>{item.payer_token ?? '(None / Unmapped)'}</Text>
          </Text>

          <Text style={styles.detailRow}>
            <Text style={styles.detailLabel}>Source: </Text>
            <Text style={styles.detailValue}>{item.source}</Text>
          </Text>

          {item.reason && (
            <Text style={styles.reasonText}>
              Reason: {item.reason}
            </Text>
          )}

          <TouchableOpacity
            style={styles.allocateBtn}
            onPress={() => {
              setSelectedEvent(item);
              setActionMessage(null);
            }}
          >
            <Ionicons name="person-add-outline" size={16} color="#ffffff" style={{ marginRight: 6 }} />
            <Text style={styles.allocateBtnText}>Manually Allocate Payment</Text>
          </TouchableOpacity>
        </View>
      ))}

      {/* Manual Allocation Drawer/Card */}
      {selectedEvent && (
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Confirm Manual Allocation</Text>
            <TouchableOpacity onPress={() => setSelectedEvent(null)}>
              <Ionicons name="close" size={22} color="#333" />
            </TouchableOpacity>
          </View>

          <Text style={styles.modalSub}>
            Allocating ₹{(selectedEvent.amount_paise / 100).toFixed(2)} (Event: {selectedEvent.event_id})
          </Text>

          <Text style={styles.inputLabel}>Target Customer ID:</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. cust_synth_raju_01"
            value={targetCustomerId}
            onChangeText={setTargetCustomerId}
            autoCapitalize="none"
          />

          <TouchableOpacity
            style={styles.confirmRow}
            onPress={() => setConfirmed(!confirmed)}
            activeOpacity={0.8}
          >
            <Ionicons
              name={confirmed ? 'checkbox' : 'square-outline'}
              size={22}
              color={confirmed ? '#0f3460' : '#888'}
            />
            <Text style={styles.confirmLabel}>
              I confirm that this payment repays the debt of this customer.
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.submitBtn, (!confirmed || submitting) && styles.submitBtnDisabled]}
            onPress={handleManualAllocate}
            disabled={!confirmed || submitting}
          >
            {submitting ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.submitBtnText}>Post Allocation to Ledger</Text>
            )}
          </TouchableOpacity>
        </View>
      )}
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
    marginBottom: 12,
  },
  title: { fontSize: 20, fontWeight: '700', color: '#0f3460' },
  refreshBtn: { flexDirection: 'row', alignItems: 'center', padding: 6 },
  refreshText: { marginLeft: 4, color: '#0f3460', fontWeight: '600', fontSize: 13 },
  disclaimerBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#e8f0fe',
    padding: 10,
    borderRadius: 8,
    marginBottom: 16,
  },
  disclaimerText: { flex: 1, fontSize: 12, color: '#0f3460', lineHeight: 16 },
  successBanner: {
    backgroundColor: '#d4edda',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#c3e6cb',
  },
  successText: { color: '#155724', fontSize: 13, fontWeight: '600' },
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
  emptyTitle: { fontSize: 16, fontWeight: '700', color: '#28a745', marginTop: 8 },
  emptySubtitle: { fontSize: 13, color: '#6c757d', textAlign: 'center', marginTop: 4 },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#dee2e6',
    elevation: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  eventAmount: { fontSize: 20, fontWeight: '800', color: '#0f3460' },
  statusBadge: {
    backgroundColor: '#fff3cd',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusBadgeText: { fontSize: 11, fontWeight: '700', color: '#856404' },
  detailRow: { fontSize: 12, color: '#495057', marginBottom: 4 },
  detailLabel: { fontWeight: '600' },
  detailValue: { fontFamily: 'monospace' },
  reasonText: {
    fontSize: 12,
    color: '#dc3545',
    backgroundColor: '#fff5f5',
    padding: 6,
    borderRadius: 4,
    marginTop: 6,
    marginBottom: 8,
  },
  allocateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0f3460',
    paddingVertical: 8,
    borderRadius: 6,
    marginTop: 8,
  },
  allocateBtnText: { color: '#ffffff', fontSize: 13, fontWeight: '600' },
  modalCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 16,
    borderWidth: 2,
    borderColor: '#0f3460',
    marginTop: 12,
    marginBottom: 20,
    elevation: 3,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  modalTitle: { fontSize: 16, fontWeight: '700', color: '#0f3460' },
  modalSub: { fontSize: 13, color: '#495057', marginBottom: 12 },
  inputLabel: { fontSize: 12, fontWeight: '600', color: '#495057', marginBottom: 4 },
  input: {
    height: 40,
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 6,
    paddingHorizontal: 12,
    fontSize: 14,
    backgroundColor: '#f8f9fa',
    marginBottom: 12,
  },
  confirmRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  confirmLabel: {
    marginLeft: 8,
    fontSize: 12,
    color: '#212529',
    flex: 1,
    lineHeight: 16,
  },
  submitBtn: {
    backgroundColor: '#28a745',
    paddingVertical: 10,
    borderRadius: 6,
    alignItems: 'center',
  },
  submitBtnDisabled: { backgroundColor: '#adb5bd' },
  submitBtnText: { color: '#ffffff', fontSize: 14, fontWeight: '700' },
});
