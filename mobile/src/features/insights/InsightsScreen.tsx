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
import { fetchInsightFacts, Persona, FactsResponse } from '@/api/ledgerClient';
import { SyntheticDataPill } from '@/components/InfoBanner';
import { formatFactComparison, formatFactDefinition, formatFactValue, formatPeriodDate } from '@/utils/formatters';

const PERSONAS: { key: Persona; label: string }[] = [
  { key: 'kirana', label: 'Kirana Store' },
  { key: 'tea_stall', label: 'Tea Stall' },
  { key: 'medical_store', label: 'Medical Store' },
];

export default function InsightsScreen() {
  const [selectedPersona, setSelectedPersona] = useState<Persona>('kirana');
  const [loading, setLoading] = useState(false);
  const [factsData, setFactsData] = useState<FactsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadFacts = useCallback(async (persona: Persona) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInsightFacts(persona);
      setFactsData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Failed to fetch insights: ${message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFacts(selectedPersona);
  }, [selectedPersona, loadFacts]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <SyntheticDataPill />

      <Text style={styles.title}>Business Insights & Facts</Text>
      <Text style={styles.subtitle}>
        Deterministic facts computed from synthetic transaction records. Not Paytm data.
      </Text>

      {/* Persona Selector Chips */}
      <Text style={styles.sectionHeader}>Select Synthetic Merchant Persona:</Text>
      <View style={styles.personaRow}>
        {PERSONAS.map((p) => {
          const isSelected = p.key === selectedPersona;
          return (
            <TouchableOpacity
              key={p.key}
              style={[styles.personaChip, isSelected && styles.personaChipSelected]}
              onPress={() => setSelectedPersona(p.key)}
            >
              <Text style={[styles.personaText, isSelected && styles.personaTextSelected]}>
                {p.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading && <ActivityIndicator size="small" color="#0f3460" style={{ marginVertical: 16 }} />}

      {factsData && !loading && (
        <>
          {/* Period & Shop Info */}
          <View style={styles.metaCard}>
            <Text style={styles.metaRow}>
              <Text style={styles.metaLabel}>Shop ID: </Text>
              <Text style={styles.metaValue}>{factsData.shop_id}</Text>
            </Text>
            <Text style={styles.metaRow}>
              <Text style={styles.metaLabel}>Data Mode: </Text>
              <Text style={styles.metaValue}>{factsData.data_mode}</Text>
            </Text>
            <Text style={styles.metaRow}>
              <Text style={styles.metaLabel}>Active Window: </Text>
              <Text style={styles.metaValue}>
                {formatPeriodDate(factsData.period.start, factsData.period.timezone)} to {formatPeriodDate(factsData.period.end, factsData.period.timezone, true)}
              </Text>
            </Text>
          </View>

          {/* Computed Facts Table */}
          <Text style={styles.sectionHeader}>Computed Provenance-Bearing Facts:</Text>
          {factsData.facts.map((fact) => (
            <View key={fact.id} style={styles.factCard}>
              <View style={styles.factHeader}>
                <Text style={styles.factLabel}>{fact.label}</Text>
                <View style={styles.factStatus}>
                  <Text style={styles.factStatusText}>{fact.status}</Text>
                </View>
              </View>

              <Text style={styles.factValue}>
                {formatFactValue(fact)}
              </Text>

              {formatFactComparison(fact) && <Text style={styles.comparisonRow}>{formatFactComparison(fact)}</Text>}

              {formatFactDefinition(fact) && <Text style={styles.factMeta}>{formatFactDefinition(fact)}</Text>}

              <Text style={styles.factMeta}>
                Source: {fact.source} · Fact ID: {fact.id}
              </Text>

              {fact.reason_unavailable && (
                <Text style={styles.unavailText}>Reason: {fact.reason_unavailable}</Text>
              )}
            </View>
          ))}

          {/* Evidence IDs */}
          <Text style={styles.sectionHeader}>Evidence IDs Used:</Text>
          <View style={styles.evidenceCard}>
            {factsData.evidence_ids.map((id) => (
              <View key={id} style={styles.evidenceBadge}>
                <Ionicons name="link-outline" size={14} color="#0f3460" style={{ marginRight: 4 }} />
                <Text style={styles.evidenceText}>{id}</Text>
              </View>
            ))}
          </View>

          {/* Caveats Section */}
          <Text style={styles.sectionHeader}>Caveats & Limitations:</Text>
          <View style={styles.caveatCard}>
            {factsData.caveats.map((c, i) => (
              <View key={i} style={styles.caveatRow}>
                <Ionicons name="information-circle-outline" size={16} color="#856404" style={{ marginRight: 6 }} />
                <Text style={styles.caveatText}>{c}</Text>
              </View>
            ))}
            <View style={styles.caveatRow}>
              <Ionicons name="alert-circle-outline" size={16} color="#856404" style={{ marginRight: 6 }} />
              <Text style={styles.caveatText}>
                Before/after metric comparisons are observational only. No causal claim is made between merchant actions and revenue lift.
              </Text>
            </View>
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8f9fa' },
  content: { padding: 16, paddingBottom: 32 },
  title: { fontSize: 20, fontWeight: '700', color: '#0f3460' },
  subtitle: { fontSize: 13, color: '#6c757d', marginTop: 2, marginBottom: 14 },
  sectionHeader: {
    fontSize: 12,
    fontWeight: '700',
    color: '#495057',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: 10,
    marginBottom: 8,
  },
  personaRow: { flexDirection: 'row', marginBottom: 14 },
  personaChip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: '#e9ecef',
    marginRight: 8,
  },
  personaChipSelected: { backgroundColor: '#0f3460' },
  personaText: { fontSize: 13, color: '#495057', fontWeight: '600' },
  personaTextSelected: { color: '#ffffff' },
  errorBanner: {
    backgroundColor: '#f8d7da',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#f5c6cb',
  },
  errorText: { color: '#721c24', fontSize: 13 },
  metaCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#dee2e6',
  },
  metaRow: { fontSize: 12, color: '#495057', marginBottom: 3 },
  metaLabel: { fontWeight: '600' },
  metaValue: { fontFamily: 'monospace' },
  factCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#dee2e6',
    elevation: 1,
  },
  factHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  factLabel: { fontSize: 14, fontWeight: '700', color: '#0f3460', flex: 1 },
  factStatus: {
    backgroundColor: '#e8f0fe',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  factStatusText: { fontSize: 11, color: '#0f3460', fontWeight: '600' },
  factValue: { fontSize: 18, fontWeight: '800', color: '#212529', marginBottom: 4 },
  comparisonRow: { fontSize: 12, color: '#6c757d', marginBottom: 4 },
  factMeta: { fontSize: 11, color: '#9aa0a6' },
  unavailText: { fontSize: 11, color: '#dc3545', marginTop: 4 },
  evidenceCard: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    backgroundColor: '#ffffff',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#dee2e6',
    marginBottom: 14,
  },
  evidenceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#e8f0fe',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  evidenceText: { fontSize: 12, color: '#0f3460', fontFamily: 'monospace' },
  caveatCard: {
    backgroundColor: '#fff3cd',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: '#ffeeba',
    marginBottom: 16,
  },
  caveatRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  caveatText: {
    fontSize: 12,
    color: '#856404',
    flex: 1,
    lineHeight: 16,
  },
});
