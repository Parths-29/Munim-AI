import React, { useState } from 'react';
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
  resolveProduct,
  createProduct,
  fetchProductStock,
  recordStockoutObservation,
  recordPhysicalCount,
  ProductStockResponse,
} from '@/api/ledgerClient';
import { SyntheticDataPill } from '@/components/InfoBanner';

export default function InventoryScreen() {
  const [searchQuery, setSearchQuery] = useState('Maggi');
  const [loading, setLoading] = useState(false);
  const [stockInfo, setStockInfo] = useState<ProductStockResponse | null>(null);
  const [foundProductId, setFoundProductId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Stock count form
  const [physicalCountInput, setPhysicalCountInput] = useState('');
  const [countSubmitting, setCountSubmitting] = useState(false);

  // Product creation form
  const [newProductName, setNewProductName] = useState('');
  const [newProductAliases, setNewProductAliases] = useState('');
  const [newProductUnit, setNewProductUnit] = useState('pack');
  const [showAddProduct, setShowAddProduct] = useState(false);

  const handleSearchProduct = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const res = await resolveProduct(searchQuery.trim());
      if (res.status === 'RESOLVED' && res.product) {
        setFoundProductId(res.product.product_id);
        const stock = await fetchProductStock(res.product.product_id);
        setStockInfo({ ...stock, product_name: res.product.name });
        setStatusMessage(`Resolved: ${res.product.name} (Unit: ${res.product.unit})`);
      } else if (res.status === 'AMBIGUOUS') {
        setErrorMessage(`Multiple products matched "${searchQuery}". Please specify an exact name.`);
        setStockInfo(null);
      } else {
        setErrorMessage(`Product "${searchQuery}" not found. You can add it below.`);
        setStockInfo(null);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMessage(`Search error: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRecordStockout = async () => {
    if (!foundProductId) {
      Alert.alert('No Product', 'Please resolve a product first.');
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await recordStockoutObservation({
        product_id: foundProductId,
        source_event_id: `evt_stockout_${Date.now()}`,
        idempotency_key: `cmd_stockout_${Date.now()}`,
        confirmed: true,
        source_utterance: `${searchQuery} khatam ho gaya`,
        source_channel: 'text',
      });
      setStatusMessage(
        `✓ Stockout observed for product ${res.product_id}. NOTE: Physical inventory is unchanged until a count is confirmed.`
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMessage(`Stockout record failed: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmPhysicalCount = async () => {
    if (!foundProductId) return;
    const qty = parseInt(physicalCountInput, 10);
    if (isNaN(qty) || qty < 0) {
      Alert.alert('Invalid Count', 'Please enter a non-negative integer count.');
      return;
    }

    setCountSubmitting(true);
    setErrorMessage(null);
    try {
      const res = await recordPhysicalCount({
        product_id: foundProductId,
        counted_quantity: qty,
        source_event_id: `evt_count_${Date.now()}`,
        idempotency_key: `cmd_count_${Date.now()}`,
        confirmed: true,
        source_utterance: `Physical count: ${qty}`,
        source_channel: 'text',
      });
      setStatusMessage(
        `✓ Physical count updated! Previous: ${res.previous_quantity}, Counted: ${res.counted_quantity}, Delta: ${res.quantity_delta}`
      );
      setPhysicalCountInput('');
      const updatedStock = await fetchProductStock(foundProductId);
      setStockInfo({ ...updatedStock, product_name: stockInfo?.product_name });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMessage(`Count update failed: ${message}`);
    } finally {
      setCountSubmitting(false);
    }
  };

  const handleCreateProduct = async () => {
    if (!newProductName.trim()) {
      Alert.alert('Missing Name', 'Product name is required.');
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    try {
      const aliases = newProductAliases
        .split(',')
        .map((a) => a.trim())
        .filter((a) => a.length > 0);
      aliases.push(newProductName.trim());

      const res = await createProduct({
        name: newProductName.trim(),
        aliases: Array.from(new Set(aliases)),
        unit: newProductUnit.trim() || 'pack',
        confirmed: true,
        idempotency_key: `cmd_create_prod_${Date.now()}`,
      });
      setStatusMessage(`✓ Product "${res.name}" created with ID: ${res.product_id}`);
      setFoundProductId(res.product_id);
      setSearchQuery(res.name);
      setShowAddProduct(false);
      setNewProductName('');
      setNewProductAliases('');
      const stock = await fetchProductStock(res.product_id);
      setStockInfo({ ...stock, product_name: res.name });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMessage(`Product creation failed: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <SyntheticDataPill />

      <Text style={styles.title}>Inventory & Stock</Text>
      <Text style={styles.subtitle}>
        KiranaOS structured stock memory. Observations do not alter on-hand stock without counted confirmation.
      </Text>

      {/* Search Bar */}
      <View style={styles.searchRow}>
        <TextInput
          style={styles.searchInput}
          placeholder="Product name or alias (e.g. Maggi)"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        <TouchableOpacity style={styles.searchBtn} onPress={handleSearchProduct} disabled={loading}>
          {loading ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.searchBtnText}>Lookup</Text>
          )}
        </TouchableOpacity>
      </View>

      {statusMessage && (
        <View style={styles.statusBox}>
          <Text style={styles.statusText}>{statusMessage}</Text>
        </View>
      )}

      {errorMessage && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{errorMessage}</Text>
        </View>
      )}

      {/* Stock Display Card */}
      {stockInfo && (
        <View style={styles.stockCard}>
          <View style={styles.stockCardHeader}>
            <Text style={styles.productName}>{stockInfo.product_name ?? 'Product'}</Text>
            <Text style={styles.stockQty}>
              {stockInfo.on_hand_quantity} {stockInfo.unit}s
            </Text>
          </View>
          <Text style={styles.stockDetails}>Product ID: {stockInfo.product_id}</Text>
          <Text style={styles.stockDetails}>Movements Count: {stockInfo.movement_count}</Text>

          {/* Action buttons */}
          <View style={styles.actionDivider} />

          <Text style={styles.actionHeader}>Actions:</Text>

          {/* 1. Stockout Observation */}
          <TouchableOpacity style={styles.stockoutBtn} onPress={handleRecordStockout} disabled={loading}>
            <Ionicons name="alert-circle-outline" size={18} color="#dc3545" style={{ marginRight: 6 }} />
            <Text style={styles.stockoutBtnText}>Report Stockout Observation ("Khatam ho gaya")</Text>
          </TouchableOpacity>
          <Text style={styles.actionNote}>
            ⚠ Note: Stockout is an observation only; it preserves auditable history without reducing verified inventory.
          </Text>

          {/* 2. Physical Count Confirmation */}
          <View style={styles.countSection}>
            <Text style={styles.countTitle}>Confirm Physical Count:</Text>
            <View style={styles.countRow}>
              <TextInput
                style={styles.countInput}
                placeholder="Counted quantity"
                keyboardType="numeric"
                value={physicalCountInput}
                onChangeText={setPhysicalCountInput}
              />
              <TouchableOpacity
                style={[styles.countBtn, countSubmitting && styles.countBtnDisabled]}
                onPress={handleConfirmPhysicalCount}
                disabled={countSubmitting}
              >
                {countSubmitting ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <Text style={styles.countBtnText}>Record Count</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      )}

      {/* Add Product Toggle */}
      <TouchableOpacity
        style={styles.toggleAddBtn}
        onPress={() => setShowAddProduct(!showAddProduct)}
      >
        <Ionicons name={showAddProduct ? 'chevron-up' : 'add-circle-outline'} size={18} color="#0f3460" />
        <Text style={styles.toggleAddText}>
          {showAddProduct ? 'Hide Add Product' : '+ Add New Product to Shop Catalog'}
        </Text>
      </TouchableOpacity>

      {showAddProduct && (
        <View style={styles.addProductCard}>
          <Text style={styles.addProductTitle}>Create Product</Text>
          <TextInput
            style={styles.input}
            placeholder="Product Name (e.g. Parle-G)"
            value={newProductName}
            onChangeText={setNewProductName}
          />
          <TextInput
            style={styles.input}
            placeholder="Aliases (comma-separated, e.g. biscuit, parle)"
            value={newProductAliases}
            onChangeText={setNewProductAliases}
          />
          <TextInput
            style={styles.input}
            placeholder="Unit (e.g. pack, kg, bottle)"
            value={newProductUnit}
            onChangeText={setNewProductUnit}
          />
          <TouchableOpacity style={styles.submitProductBtn} onPress={handleCreateProduct} disabled={loading}>
            <Text style={styles.submitProductText}>Save Product</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8f9fa' },
  content: { padding: 16, paddingBottom: 32 },
  title: { fontSize: 20, fontWeight: '700', color: '#0f3460' },
  subtitle: { fontSize: 13, color: '#6c757d', marginTop: 2, marginBottom: 16 },
  searchRow: { flexDirection: 'row', marginBottom: 12 },
  searchInput: {
    flex: 1,
    height: 42,
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 6,
    paddingHorizontal: 12,
    backgroundColor: '#ffffff',
    fontSize: 14,
    marginRight: 8,
  },
  searchBtn: {
    backgroundColor: '#0f3460',
    paddingHorizontal: 16,
    borderRadius: 6,
    justifyContent: 'center',
    alignItems: 'center',
  },
  searchBtnText: { color: '#ffffff', fontWeight: '600', fontSize: 13 },
  statusBox: {
    backgroundColor: '#d4edda',
    padding: 10,
    borderRadius: 6,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#c3e6cb',
  },
  statusText: { color: '#155724', fontSize: 13 },
  errorBox: {
    backgroundColor: '#f8d7da',
    padding: 10,
    borderRadius: 6,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#f5c6cb',
  },
  errorText: { color: '#721c24', fontSize: 13 },
  stockCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#dee2e6',
    elevation: 2,
  },
  stockCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  productName: { fontSize: 18, fontWeight: '700', color: '#0f3460' },
  stockQty: { fontSize: 18, fontWeight: '800', color: '#28a745' },
  stockDetails: { fontSize: 12, color: '#6c757d', marginBottom: 2 },
  actionDivider: { height: 1, backgroundColor: '#dee2e6', marginVertical: 12 },
  actionHeader: { fontSize: 13, fontWeight: '700', color: '#495057', marginBottom: 8 },
  stockoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff5f5',
    borderWidth: 1,
    borderColor: '#dc3545',
    paddingVertical: 8,
    borderRadius: 6,
    marginBottom: 4,
  },
  stockoutBtnText: { color: '#dc3545', fontWeight: '600', fontSize: 13 },
  actionNote: { fontSize: 11, color: '#856404', backgroundColor: '#fff3cd', padding: 6, borderRadius: 4, marginBottom: 12 },
  countSection: { marginTop: 4 },
  countTitle: { fontSize: 13, fontWeight: '600', color: '#333', marginBottom: 6 },
  countRow: { flexDirection: 'row' },
  countInput: {
    flex: 1,
    height: 40,
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 6,
    paddingHorizontal: 12,
    fontSize: 14,
    marginRight: 8,
    backgroundColor: '#f8f9fa',
  },
  countBtn: {
    backgroundColor: '#28a745',
    paddingHorizontal: 14,
    borderRadius: 6,
    justifyContent: 'center',
    alignItems: 'center',
  },
  countBtnDisabled: { backgroundColor: '#adb5bd' },
  countBtnText: { color: '#ffffff', fontWeight: '600', fontSize: 13 },
  toggleAddBtn: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
  toggleAddText: { marginLeft: 6, color: '#0f3460', fontWeight: '600', fontSize: 13 },
  addProductCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 14,
    borderWidth: 1,
    borderColor: '#dee2e6',
    marginTop: 6,
  },
  addProductTitle: { fontSize: 15, fontWeight: '700', color: '#0f3460', marginBottom: 10 },
  input: {
    height: 40,
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 6,
    paddingHorizontal: 12,
    fontSize: 14,
    backgroundColor: '#f8f9fa',
    marginBottom: 10,
  },
  submitProductBtn: {
    backgroundColor: '#0f3460',
    paddingVertical: 10,
    borderRadius: 6,
    alignItems: 'center',
  },
  submitProductText: { color: '#ffffff', fontWeight: '600', fontSize: 13 },
});
