import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Modal,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';
import { PaytmCard } from '@/components/common/PaytmCard';
import { Badge } from '@/components/common/Badge';
import { useDemoData, DemoProduct } from '@/context/DemoDataContext';

type StockFilter = 'all' | 'low_stock' | 'out_of_stock';

interface StockScreenProps {
  onOpenScanBill?: () => void;
}

export const StockScreen: React.FC<StockScreenProps> = ({ onOpenScanBill }) => {
  const {
    products,
    reportStockout,
    recordPhysicalCount,
    activityEvents,
  } = useDemoData();

  const [activeFilter, setActiveFilter] = useState<StockFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<DemoProduct | null>(null);

  // Modals
  const [stockoutModalVisible, setStockoutModalVisible] = useState(false);
  const [physicalCountModalVisible, setPhysicalCountModalVisible] = useState(false);
  const [newCountInput, setNewCountInput] = useState('');
  const [countReviewing, setCountReviewing] = useState(false);

  const [outflowModalVisible, setOutflowModalVisible] = useState(false);
  const [outflowQtyInput, setOutflowQtyInput] = useState('');
  const [outflowReason, setOutflowReason] = useState<'sale' | 'wastage' | 'self_use' | 'supplier_return'>('sale');

  // Filter products
  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.aliases.some((a) => a.includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;
    if (activeFilter === 'low_stock') return p.onHand <= p.reorderThreshold && p.onHand > 0;
    if (activeFilter === 'out_of_stock') return p.onHand === 0;
    return true;
  });

  const lowStockCount = products.filter((p) => p.onHand <= p.reorderThreshold && p.onHand > 0).length;
  const outOfStockCount = products.filter((p) => p.onHand === 0).length;

  // Handler: Report Stockout (Observation Only)
  const handleConfirmStockoutObservation = async () => {
    if (!selectedProduct) return;
    await reportStockout(selectedProduct.id);
    setSelectedProduct((prev) => (prev ? { ...prev, lastStockoutObservation: 'Reported just now' } : null));
    setStockoutModalVisible(false);
    Alert.alert(
      'Stockout Observation Saved',
      `Observation noted for ${selectedProduct.name}. As per inventory integrity rules, physical on-hand quantity remains unchanged at ${selectedProduct.onHand} ${selectedProduct.unit}s until a physical count is confirmed.`
    );
  };

  // Handler: Confirm Physical Count
  const handleConfirmPhysicalCount = async () => {
    if (!selectedProduct) return;
    const count = parseInt(newCountInput, 10);
    if (isNaN(count) || count < 0) {
      Alert.alert('Invalid', 'Please enter a valid count quantity.');
      return;
    }

    await recordPhysicalCount(selectedProduct.id, count);
    setSelectedProduct((prev) => (prev ? { ...prev, onHand: count, lastStockoutObservation: undefined } : null));
    setNewCountInput('');
    setCountReviewing(false);
    setPhysicalCountModalVisible(false);
  };

  // Handler: Record Outflow
  const handleConfirmOutflow = async () => {
    if (!selectedProduct) return;
    const qty = parseInt(outflowQtyInput, 10);
    if (isNaN(qty) || qty <= 0 || qty > selectedProduct.onHand) {
      Alert.alert('Invalid', `Quantity must be between 1 and ${selectedProduct.onHand}.`);
      return;
    }
    const newQty = selectedProduct.onHand - qty;
    await recordPhysicalCount(selectedProduct.id, newQty);
    setSelectedProduct((prev) => (prev ? { ...prev, onHand: newQty } : null));
    setOutflowQtyInput('');
    setOutflowModalVisible(false);
  };

  return (
    <View style={styles.container}>
      {selectedProduct ? (
        /* ── PRODUCT DETAIL VIEW ─────────────────────────────────────── */
        <ScrollView style={styles.detailScroll} contentContainerStyle={styles.detailContent}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => setSelectedProduct(null)}
          >
            <Ionicons name="arrow-back" size={20} color={colors.navy} />
            <Text style={styles.backButtonText}>All Products</Text>
          </TouchableOpacity>

          {/* Product Profile Card */}
          <PaytmCard style={styles.productProfileCard}>
            <View style={styles.productHeaderRow}>
              <View style={styles.productIconCircle}>
                <Ionicons name="cube" size={24} color={colors.navy} />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.productDetailName}>{selectedProduct.name}</Text>
                <Text style={styles.productCategory}>FMCG / Packaged Goods</Text>
                <Text style={styles.productUpdated}>Last Count: {selectedProduct.lastCountUpdate}</Text>
              </View>
            </View>

            {/* Current Stock Banner */}
            <View style={styles.onHandBanner}>
              <Text style={styles.onHandLabel}>Recorded On-Hand Quantity</Text>
              <Text style={styles.onHandValue}>
                {selectedProduct.onHand} <Text style={{ fontSize: 16 }}>{selectedProduct.unit}s</Text>
              </Text>
              <View style={styles.reorderRow}>
                <Text style={styles.reorderText}>
                  Reorder Threshold: {selectedProduct.reorderThreshold} {selectedProduct.unit}s · Selling Price: ₹
                  {(selectedProduct.sellingPricePaise / 100).toFixed(2)}
                </Text>
              </View>
            </View>

            {selectedProduct.lastStockoutObservation && (
              <View style={styles.stockoutObsPill}>
                <Ionicons name="warning" size={14} color="#92400E" />
                <Text style={styles.stockoutObsText}>
                  Stockout reported: {selectedProduct.lastStockoutObservation} (Observation only)
                </Text>
              </View>
            )}

            {/* 4 Dedicated Inventory Actions */}
            <Text style={styles.actionsSubheading}>Stock Management Actions</Text>
            <View style={styles.inventoryActionGrid}>
              {/* Action 1: Physical Count */}
              <TouchableOpacity
                style={styles.invActionTile}
                onPress={() => {
                  setNewCountInput(selectedProduct.onHand.toString());
                  setCountReviewing(false);
                  setPhysicalCountModalVisible(true);
                }}
              >
                <Ionicons name="clipboard-outline" size={20} color={colors.navy} />
                <Text style={styles.invActionTitle}>Physical Count</Text>
                <Text style={styles.invActionSub}>Audit & verify</Text>
              </TouchableOpacity>

              {/* Action 2: Report Stockout */}
              <TouchableOpacity
                style={styles.invActionTile}
                onPress={() => setStockoutModalVisible(true)}
              >
                <Ionicons name="alert-circle-outline" size={20} color={colors.warning} />
                <Text style={styles.invActionTitle}>Report Stockout</Text>
                <Text style={styles.invActionSub}>Observation only</Text>
              </TouchableOpacity>

              {/* Action 3: Add Stock (Inward) */}
              <TouchableOpacity
                style={styles.invActionTile}
                onPress={onOpenScanBill}
              >
                <Ionicons name="add-circle-outline" size={20} color={colors.jamaGreen} />
                <Text style={styles.invActionTitle}>Add Stock</Text>
                <Text style={styles.invActionSub}>Scan inward bill</Text>
              </TouchableOpacity>

              {/* Action 4: Record Outflow */}
              <TouchableOpacity
                style={styles.invActionTile}
                onPress={() => setOutflowModalVisible(true)}
              >
                <Ionicons name="remove-circle-outline" size={20} color={colors.udhaarRed} />
                <Text style={styles.invActionTitle}>Record Outflow</Text>
                <Text style={styles.invActionSub}>Wastage / Return</Text>
              </TouchableOpacity>
            </View>

            {/* Reorder Suggestion (Caveat stated) */}
            {selectedProduct.onHand <= selectedProduct.reorderThreshold && (
              <View style={styles.reorderSuggestionCard}>
                <View style={styles.reorderHeader}>
                  <Ionicons name="bulb-outline" size={16} color={colors.deepCyan} />
                  <Text style={styles.reorderTitle}>Reorder Suggestion</Text>
                  <Badge label="Recommendation" variant="neutral" />
                </View>
                <Text style={styles.reorderDesc}>
                  Suggest ordering 24 {selectedProduct.unit}s from Krishna FMCG based on 14-day observed velocity.
                </Text>
                <Text style={styles.reorderCaveat}>
                  *Suggestion only. Munim-AI never automatically places supplier orders.
                </Text>
              </View>
            )}
          </PaytmCard>

          {/* Movement History */}
          <Text style={styles.movementSectionTitle}>Audit & Movement Stream</Text>
          <PaytmCard style={styles.movementCard}>
            {activityEvents
              .filter((e) => e.summary.toLowerCase().includes(selectedProduct.name.toLowerCase().split(' ')[0]))
              .map((item, idx) => (
                <View key={item.event_id || idx}>
                  <View style={styles.movementRow}>
                    <Ionicons name="cube-outline" size={16} color={colors.navy} />
                    <View style={{ flex: 1, marginLeft: 10 }}>
                      <Text style={styles.movementSummary}>{item.summary}</Text>
                      <Text style={styles.movementTimestamp}>
                        {new Date(item.created_at).toLocaleDateString()} · {item.source_channel}
                      </Text>
                    </View>
                    <Badge label={item.status} variant="success" />
                  </View>
                  {idx < activityEvents.length - 1 && <View style={styles.movementDivider} />}
                </View>
              ))}
          </PaytmCard>
        </ScrollView>
      ) : (
        /* ── STOCK LIST VIEW ────────────────────────────────────────── */
        <ScrollView style={styles.listScroll} contentContainerStyle={styles.listContent}>
          {/* Summary KPIs Banner */}
          <PaytmCard variant="paleBlue" style={styles.kpiCard}>
            <View style={styles.kpiRow}>
              <View style={styles.kpiCol}>
                <Text style={styles.kpiLabel}>TOTAL PRODUCTS</Text>
                <Text style={styles.kpiValue}>{products.length}</Text>
              </View>
              <View style={styles.kpiBorder} />
              <View style={styles.kpiCol}>
                <Text style={styles.kpiLabel}>LOW STOCK</Text>
                <Text style={[styles.kpiValue, { color: colors.warning }]}>{lowStockCount}</Text>
              </View>
              <View style={styles.kpiBorder} />
              <View style={styles.kpiCol}>
                <Text style={styles.kpiLabel}>OUT OF STOCK</Text>
                <Text style={[styles.kpiValue, { color: colors.error }]}>{outOfStockCount}</Text>
              </View>
            </View>
          </PaytmCard>

          {/* Search Bar */}
          <View style={styles.searchBar}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput
              style={styles.searchInput}
              value={searchQuery}
              onChangeText={setSearchQuery}
              placeholder="Search product by name, brand, alias..."
              placeholderTextColor={colors.textMuted}
            />
          </View>

          {/* Filter Pills */}
          <View style={styles.filterPillsRow}>
            <TouchableOpacity
              style={[styles.filterPill, activeFilter === 'all' && styles.filterPillActive]}
              onPress={() => setActiveFilter('all')}
            >
              <Text style={[styles.filterPillText, activeFilter === 'all' && styles.filterPillTextActive]}>
                All Items ({products.length})
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.filterPill, activeFilter === 'low_stock' && styles.filterPillActive]}
              onPress={() => setActiveFilter('low_stock')}
            >
              <Text style={[styles.filterPillText, activeFilter === 'low_stock' && styles.filterPillTextActive]}>
                Low Stock ({lowStockCount})
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.filterPill, activeFilter === 'out_of_stock' && styles.filterPillActive]}
              onPress={() => setActiveFilter('out_of_stock')}
            >
              <Text style={[styles.filterPillText, activeFilter === 'out_of_stock' && styles.filterPillTextActive]}>
                Out of Stock ({outOfStockCount})
              </Text>
            </TouchableOpacity>
          </View>

          {/* Product Items List */}
          {filteredProducts.map((p) => {
            const isLow = p.onHand <= p.reorderThreshold && p.onHand > 0;
            const isOut = p.onHand === 0;

            return (
              <TouchableOpacity
                key={p.id}
                onPress={() => setSelectedProduct(p)}
                activeOpacity={0.7}
              >
                <PaytmCard style={styles.productRowCard}>
                  <View style={styles.productRow}>
                    <View style={styles.productAvatarCircle}>
                      <Ionicons name="cube-outline" size={20} color={colors.navy} />
                    </View>

                    <View style={{ flex: 1, marginHorizontal: 12 }}>
                      <Text style={styles.productName}>{p.name}</Text>
                      <Text style={styles.productUnitCost}>
                        Selling at ₹{(p.sellingPricePaise / 100).toFixed(2)} / {p.unit}
                      </Text>
                      <Text style={styles.productUpdatedSub}>Updated: {p.lastCountUpdate}</Text>
                    </View>

                    <View style={{ alignItems: 'flex-end' }}>
                      <Text style={styles.qtyLabel}>On-Hand</Text>
                      <Text style={[styles.qtyValue, isLow && { color: colors.warning }, isOut && { color: colors.error }]}>
                        {p.onHand} {p.unit}s
                      </Text>
                      <Badge
                        label={isOut ? 'Out of Stock' : isLow ? 'Low Stock' : 'In Stock'}
                        variant={isOut ? 'error' : isLow ? 'warning' : 'success'}
                      />
                    </View>
                  </View>
                </PaytmCard>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}

      {/* ── MODAL: REPORT STOCKOUT (Observation Only) ──────────────── */}
      <Modal visible={stockoutModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalSheetHeader}>
              <Text style={styles.modalSheetTitle}>Report Stockout Observation</Text>
              <TouchableOpacity onPress={() => setStockoutModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <View style={styles.noticeBox}>
              <Ionicons name="shield-checkmark-outline" size={20} color={colors.navy} />
              <Text style={styles.noticeBoxText}>
                Observation Only: Recording a stockout observation logs a merchant sighting. It does NOT automatically
                change recorded physical quantity until a physical count is audited.
              </Text>
            </View>

            <Text style={styles.stockoutTargetText}>Product: {selectedProduct?.name}</Text>
            <Text style={styles.stockoutCurrentText}>Current Recorded On-Hand: {selectedProduct?.onHand} {selectedProduct?.unit}s</Text>

            <TouchableOpacity
              style={styles.confirmStockoutBtn}
              onPress={handleConfirmStockoutObservation}
            >
              <Text style={styles.confirmStockoutBtnText}>Save Stockout Observation</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ── MODAL: PHYSICAL COUNT (Audit write) ─────────────────────── */}
      <Modal visible={physicalCountModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalSheetHeader}>
              <Text style={styles.modalSheetTitle}>Physical Stock Count</Text>
              <TouchableOpacity onPress={() => setPhysicalCountModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSheetSub}>
              Physical counts explicitly update the recorded inventory on-hand quantity.
            </Text>

            <Text style={styles.inputLabel}>Enter Actual Counted Quantity ({selectedProduct?.unit}s) *</Text>
            <TextInput
              style={[styles.modalTextInput, styles.qtyInputBig]}
              placeholder="e.g. 10"
              keyboardType="number-pad"
              value={newCountInput}
              onChangeText={setNewCountInput}
            />

            {!countReviewing ? (
              <TouchableOpacity
                style={styles.submitModalBtn}
                onPress={() => {
                  const qty = parseInt(newCountInput, 10);
                  if (isNaN(qty) || qty < 0) {
                    Alert.alert('Invalid', 'Enter valid quantity.');
                    return;
                  }
                  setCountReviewing(true);
                }}
              >
                <Text style={styles.submitModalBtnText}>Review Count Update →</Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.reviewBox}>
                <Badge label="Not saved yet" variant="notSaved" />
                <Text style={styles.reviewCountNumber}>
                  {newCountInput} {selectedProduct?.unit}s
                </Text>
                <Text style={styles.reviewCountProduct}>{selectedProduct?.name}</Text>
                <Text style={styles.reviewDiffText}>
                  Previous count was {selectedProduct?.onHand}. Delta: {parseInt(newCountInput, 10) - (selectedProduct?.onHand || 0)}
                </Text>

                <View style={styles.modalActionButtonsRow}>
                  <TouchableOpacity
                    style={styles.modalBackBtn}
                    onPress={() => setCountReviewing(false)}
                  >
                    <Text style={styles.modalBackBtnText}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.modalConfirmBtn}
                    onPress={handleConfirmPhysicalCount}
                  >
                    <Text style={styles.modalConfirmBtnText}>Confirm Count</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>
        </View>
      </Modal>

      {/* ── MODAL: RECORD OUTFLOW ───────────────────────────────────── */}
      <Modal visible={outflowModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalSheetHeader}>
              <Text style={styles.modalSheetTitle}>Record Stock Outflow</Text>
              <TouchableOpacity onPress={() => setOutflowModalVisible(false)}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Quantity ({selectedProduct?.unit}s) *</Text>
            <TextInput
              style={styles.modalTextInput}
              placeholder="e.g. 2"
              keyboardType="number-pad"
              value={outflowQtyInput}
              onChangeText={setOutflowQtyInput}
            />

            <Text style={styles.inputLabel}>Reason for Outflow</Text>
            <View style={styles.reasonRow}>
              {(['sale', 'wastage', 'self_use', 'supplier_return'] as const).map((r) => (
                <TouchableOpacity
                  key={r}
                  style={[styles.reasonPill, outflowReason === r && styles.reasonPillActive]}
                  onPress={() => setOutflowReason(r)}
                >
                  <Text style={[styles.reasonPillText, outflowReason === r && styles.reasonPillTextActive]}>
                    {r.replace('_', ' ').toUpperCase()}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity style={styles.submitModalBtn} onPress={handleConfirmOutflow}>
              <Text style={styles.submitModalBtnText}>Confirm Outflow</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listScroll: { flex: 1 },
  listContent: { padding: spacing.screenPadding, paddingBottom: 40 },
  detailScroll: { flex: 1 },
  detailContent: { padding: spacing.screenPadding, paddingBottom: 40 },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  backButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.navy,
  },
  kpiCard: { marginBottom: 14 },
  kpiRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  kpiCol: { flex: 1, alignItems: 'center' },
  kpiBorder: { width: 1, height: '70%', backgroundColor: colors.borderSubtle },
  kpiLabel: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  kpiValue: { fontSize: 20, fontWeight: '900', color: colors.navy, marginTop: 2 },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radii.input,
    paddingHorizontal: 12,
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 12,
  },
  searchInput: { flex: 1, marginLeft: 8, fontSize: 13, color: colors.textMain },
  filterPillsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  filterPill: {
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterPillActive: {
    backgroundColor: colors.paleBlue,
    borderColor: colors.primaryCyan,
  },
  filterPillText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  filterPillTextActive: {
    color: colors.navy,
    fontWeight: '800',
  },
  productRowCard: {
    marginBottom: 8,
    padding: 12,
  },
  productRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  productAvatarCircle: {
    width: 42,
    height: 42,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  productName: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textMain,
  },
  productUnitCost: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  productUpdatedSub: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 2,
  },
  qtyLabel: {
    fontSize: 10,
    color: colors.textSecondary,
  },
  qtyValue: {
    fontSize: 16,
    fontWeight: '900',
    color: colors.navy,
    marginVertical: 1,
  },
  productProfileCard: {
    marginBottom: 16,
  },
  productHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  productIconCircle: {
    width: 50,
    height: 50,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: colors.primaryCyan,
  },
  productDetailName: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.navy,
  },
  productCategory: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 1,
  },
  productUpdated: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  onHandBanner: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 14,
    alignItems: 'center',
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  onHandLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  onHandValue: {
    fontSize: 32,
    fontWeight: '900',
    color: colors.navy,
    marginVertical: 4,
  },
  reorderRow: {
    marginTop: 2,
  },
  reorderText: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  stockoutObsPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.warningSurface,
    borderRadius: radii.cardSmall,
    padding: 10,
    marginBottom: 14,
    gap: 6,
  },
  stockoutObsText: {
    fontSize: 12,
    color: '#92400E',
    fontWeight: '600',
    flex: 1,
  },
  actionsSubheading: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.navy,
    marginBottom: 10,
  },
  inventoryActionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  invActionTile: {
    width: '48%',
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.cardSmall,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  invActionTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.textMain,
    marginTop: 6,
  },
  invActionSub: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  reorderSuggestionCard: {
    backgroundColor: colors.paleBlue,
    borderRadius: radii.cardSmall,
    padding: 12,
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  reorderHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  reorderTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.navy,
    flex: 1,
    marginLeft: 6,
  },
  reorderDesc: {
    fontSize: 12,
    color: colors.textMain,
    lineHeight: 16,
  },
  reorderCaveat: {
    fontSize: 10,
    color: colors.textSecondary,
    fontStyle: 'italic',
    marginTop: 6,
  },
  movementSectionTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.navy,
    marginBottom: 10,
  },
  movementCard: {
    padding: 12,
  },
  movementRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
  },
  movementSummary: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textMain,
  },
  movementTimestamp: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  movementDivider: {
    height: 1,
    backgroundColor: colors.borderSubtle,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 46, 110, 0.45)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.card,
    borderTopRightRadius: radii.card,
    padding: 20,
    ...shadows.medium,
  },
  modalSheetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  modalSheetTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.navy,
  },
  modalSheetSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 14,
  },
  noticeBox: {
    flexDirection: 'row',
    backgroundColor: colors.paleBlue,
    borderRadius: radii.cardSmall,
    padding: 12,
    gap: 8,
    marginBottom: 14,
  },
  noticeBoxText: {
    fontSize: 12,
    color: colors.navy,
    flex: 1,
    lineHeight: 16,
  },
  stockoutTargetText: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textMain,
  },
  stockoutCurrentText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: 16,
  },
  confirmStockoutBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  confirmStockoutBtnText: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textWhite,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 6,
  },
  modalTextInput: {
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.input,
    paddingHorizontal: 12,
    fontSize: 14,
    color: colors.textMain,
    marginBottom: 14,
  },
  qtyInputBig: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.navy,
    height: 52,
  },
  submitModalBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 14,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  submitModalBtnText: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textWhite,
  },
  reviewBox: {
    backgroundColor: colors.surfaceSubtle,
    borderRadius: radii.card,
    padding: 16,
    alignItems: 'center',
    marginBottom: 10,
  },
  reviewCountNumber: {
    fontSize: 28,
    fontWeight: '900',
    color: colors.navy,
    marginVertical: 6,
  },
  reviewCountProduct: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textMain,
  },
  reviewDiffText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: 16,
  },
  modalActionButtonsRow: {
    flexDirection: 'row',
    gap: 10,
    width: '100%',
  },
  modalBackBtn: {
    flex: 1,
    backgroundColor: '#F1F5F9',
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  modalBackBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  modalConfirmBtn: {
    flex: 2,
    backgroundColor: colors.navy,
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
  },
  modalConfirmBtnText: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.textWhite,
  },
  reasonRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 16,
  },
  reasonPill: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceSubtle,
    borderWidth: 1,
    borderColor: colors.border,
  },
  reasonPillActive: {
    backgroundColor: colors.navy,
    borderColor: colors.navy,
  },
  reasonPillText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  reasonPillTextActive: {
    color: colors.textWhite,
  },
});
