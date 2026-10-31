import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, spacing } from '@/theme/theme';
import { useDemoData } from '@/context/DemoDataContext';
import { Badge } from '@/components/common/Badge';

interface SearchModalProps {
  visible: boolean;
  onClose: () => void;
  onSelectCustomer: (customerId: string) => void;
  onSelectProduct: (productId: string) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  visible,
  onClose,
  onSelectCustomer,
  onSelectProduct,
}) => {
  const { customers, products } = useDemoData();
  const [query, setQuery] = useState('');

  const trimmed = query.trim().toLowerCase();

  const matchingCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(trimmed) ||
      c.aliases.some((a) => a.toLowerCase().includes(trimmed))
  );

  const matchingProducts = products.filter(
    (p) =>
      p.name.toLowerCase().includes(trimmed) ||
      p.aliases.some((a) => a.toLowerCase().includes(trimmed))
  );

  return (
    <Modal visible={visible} animationType="slide">
      <View style={styles.container}>
        {/* Top Search Input */}
        <View style={styles.searchHeader}>
          <TouchableOpacity onPress={onClose} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={22} color={colors.navy} />
          </TouchableOpacity>

          <View style={styles.inputWrapper}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput
              style={styles.searchInput}
              value={query}
              onChangeText={setQuery}
              placeholder="Search customers, products or actions..."
              placeholderTextColor={colors.textMuted}
              autoFocus
            />
            {query.length > 0 && (
              <TouchableOpacity onPress={() => setQuery('')}>
                <Ionicons name="close-circle" size={18} color={colors.textMuted} />
              </TouchableOpacity>
            )}
          </View>
        </View>

        <ScrollView style={styles.resultsScroll} contentContainerStyle={styles.resultsContent}>
          {query.length === 0 ? (
            <View style={styles.suggestionsBox}>
              <Text style={styles.sectionTitle}>Recent / Popular Searches</Text>
              <View style={styles.chipRow}>
                {['Raju bhai', 'Maggi', 'Add Udhaar', 'Record Jama', 'Parle-G', 'Payment Review'].map((item) => (
                  <TouchableOpacity
                    key={item}
                    style={styles.chip}
                    onPress={() => setQuery(item)}
                  >
                    <Ionicons name="time-outline" size={13} color={colors.navy} />
                    <Text style={styles.chipText}>{item}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ) : (
            <>
              {/* Customers Section */}
              {matchingCustomers.length > 0 && (
                <View style={styles.resultGroup}>
                  <Text style={styles.sectionTitle}>Customers ({matchingCustomers.length})</Text>
                  {matchingCustomers.map((c) => (
                    <TouchableOpacity
                      key={c.id}
                      style={styles.resultItem}
                      onPress={() => {
                        onClose();
                        onSelectCustomer(c.id);
                      }}
                    >
                      <View style={styles.resultIcon}>
                        <Ionicons name="person-outline" size={18} color={colors.navy} />
                      </View>
                      <View style={{ flex: 1, marginLeft: 10 }}>
                        <Text style={styles.itemTitle}>{c.name}</Text>
                        <Text style={styles.itemSub}>{c.phone}</Text>
                      </View>
                      <Text style={[styles.dueAmount, { color: c.amountDuePaise > 0 ? colors.udhaarRed : colors.success }]}>
                        Due: ₹{(c.amountDuePaise / 100).toFixed(2)}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {/* Products Section */}
              {matchingProducts.length > 0 && (
                <View style={styles.resultGroup}>
                  <Text style={styles.sectionTitle}>Products ({matchingProducts.length})</Text>
                  {matchingProducts.map((p) => (
                    <TouchableOpacity
                      key={p.id}
                      style={styles.resultItem}
                      onPress={() => {
                        onClose();
                        onSelectProduct(p.id);
                      }}
                    >
                      <View style={styles.resultIcon}>
                        <Ionicons name="cube-outline" size={18} color={colors.navy} />
                      </View>
                      <View style={{ flex: 1, marginLeft: 10 }}>
                        <Text style={styles.itemTitle}>{p.name}</Text>
                        <Text style={styles.itemSub}>Stock: {p.onHand} {p.unit}s</Text>
                      </View>
                      <Badge
                        label={p.onHand <= p.reorderThreshold ? 'Low Stock' : 'In Stock'}
                        variant={p.onHand <= p.reorderThreshold ? 'warning' : 'success'}
                      />
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {matchingCustomers.length === 0 && matchingProducts.length === 0 && (
                <View style={styles.noResultsBox}>
                  <Ionicons name="search-outline" size={36} color={colors.textMuted} />
                  <Text style={styles.noResultsTitle}>No exact match found</Text>
                  <Text style={styles.noResultsSub}>Try typing a customer alias or product name.</Text>
                </View>
              )}
            </>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  searchHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.screenPadding,
    paddingTop: 14,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: { padding: 4, marginRight: 8 },
  inputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.pill,
    paddingHorizontal: 12,
    height: 42,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchInput: { flex: 1, marginLeft: 8, fontSize: 14, color: colors.textMain },
  resultsScroll: { flex: 1 },
  resultsContent: { padding: spacing.screenPadding },
  suggestionsBox: { marginTop: 10 },
  sectionTitle: { fontSize: 13, fontWeight: '800', color: colors.navy, marginBottom: 10 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.paleBlue,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    gap: 6,
    borderWidth: 1,
    borderColor: '#CCE7F6',
  },
  chipText: { fontSize: 12, fontWeight: '700', color: colors.navy },
  resultGroup: { marginBottom: 18 },
  resultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 12,
    borderRadius: radii.cardSmall,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 8,
  },
  resultIcon: {
    width: 36,
    height: 36,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemTitle: { fontSize: 14, fontWeight: '800', color: colors.textMain },
  itemSub: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  dueAmount: { fontSize: 13, fontWeight: '800' },
  noResultsBox: { alignItems: 'center', paddingVertical: 50 },
  noResultsTitle: { fontSize: 16, fontWeight: '800', color: colors.navy, marginTop: 10 },
  noResultsSub: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },
});

