import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows, spacing, typography } from '@/theme/theme';

export type ShopPersona = 'kirana' | 'tea_stall' | 'medical_store';

interface PaytmHeaderProps {
  currentPersona: ShopPersona;
  onSelectPersona: (persona: ShopPersona) => void;
  onOpenSearch?: () => void;
}

const PERSONA_NAMES: Record<ShopPersona, { name: string; subtitle: string; icon: keyof typeof Ionicons.glyphMap }> = {
  kirana: { name: 'Sharma Kirana Store', subtitle: 'Kirana & FMCG', icon: 'storefront' },
  tea_stall: { name: 'Chai Point Corner', subtitle: 'Tea & Snacks', icon: 'cafe' },
  medical_store: { name: 'Gupta Medical Hall', subtitle: 'Pharmacy & Wellness', icon: 'medkit' },
};

export const PaytmHeader: React.FC<PaytmHeaderProps> = ({
  currentPersona,
  onSelectPersona,
  onOpenSearch,
}) => {
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const shop = PERSONA_NAMES[currentPersona];

  return (
    <View style={styles.container}>
      {/* Top Brand Bar */}
      <View style={styles.topRow}>
        <View style={styles.brandGroup}>
          <View style={styles.brandPill}>
            <Text style={styles.brandTitle}>Munim-AI</Text>
          </View>
          <View style={styles.demoBadge}>
            <Text style={styles.demoBadgeText}>Hackathon Demo</Text>
          </View>
        </View>

        {/* Soundbox / Device status */}
        <View style={styles.soundboxPill}>
          <View style={styles.greenDot} />
          <Ionicons name="volume-medium" size={13} color={colors.navy} />
          <Text style={styles.soundboxText}>Soundbox Active</Text>
        </View>
      </View>

      {/* Merchant Profile & Persona Bar */}
      <View style={styles.merchantBar}>
        <TouchableOpacity
          style={styles.merchantInfo}
          onPress={() => setPickerOpen(true)}
          activeOpacity={0.8}
          accessibilityLabel="Switch shop persona"
        >
          <View style={styles.avatar}>
            <Ionicons name={shop.icon} size={22} color={colors.navy} />
          </View>
          <View style={styles.nameBlock}>
            <View style={styles.nameRow}>
              <Text style={styles.shopName} numberOfLines={1}>{shop.name}</Text>
              <Ionicons name="chevron-down" size={16} color={colors.navy} style={{ marginLeft: 4 }} />
            </View>
            <Text style={styles.shopSub}>{shop.subtitle} · Tap to switch</Text>
          </View>
        </TouchableOpacity>

        {onOpenSearch && (
          <TouchableOpacity
            style={styles.searchIconButton}
            onPress={onOpenSearch}
            accessibilityLabel="Search"
          >
            <Ionicons name="search-outline" size={20} color={colors.navy} />
          </TouchableOpacity>
        )}
      </View>

      {/* Persona Switcher Modal */}
      <Modal visible={pickerOpen} transparent animationType="fade">
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setPickerOpen(false)}
        >
          <View style={styles.modalSheet}>
            <Text style={styles.modalHeading}>Select Shop Demo Persona</Text>
            <Text style={styles.modalSub}>Switching personas updates synthetic inventory and transaction profiles.</Text>

            {(Object.keys(PERSONA_NAMES) as ShopPersona[]).map((key) => {
              const item = PERSONA_NAMES[key];
              const isSelected = key === currentPersona;
              return (
                <TouchableOpacity
                  key={key}
                  style={[styles.personaOption, isSelected && styles.personaOptionActive]}
                  onPress={() => {
                    onSelectPersona(key);
                    setPickerOpen(false);
                  }}
                >
                  <View style={[styles.optionAvatar, isSelected && styles.optionAvatarActive]}>
                    <Ionicons name={item.icon} size={20} color={isSelected ? colors.textWhite : colors.navy} />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={[styles.optionName, isSelected && styles.optionNameActive]}>{item.name}</Text>
                    <Text style={styles.optionSub}>{item.subtitle}</Text>
                  </View>
                  {isSelected && <Ionicons name="checkmark-circle" size={22} color={colors.primaryCyan} />}
                </TouchableOpacity>
              );
            })}

            <TouchableOpacity style={styles.closeBtn} onPress={() => setPickerOpen(false)}>
              <Text style={styles.closeBtnText}>Done</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.paleBlue,
    paddingTop: 10,
    paddingHorizontal: spacing.screenPadding,
    paddingBottom: 14,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  brandGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  brandPill: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  brandTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.navy,
    letterSpacing: -0.3,
  },
  demoBadge: {
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  demoBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textSecondary,
    letterSpacing: 0.2,
  },
  soundboxPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: radii.pill,
    gap: 5,
    borderWidth: 1,
    borderColor: colors.border,
  },
  greenDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.success,
  },
  soundboxText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.navy,
  },
  merchantBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  merchantInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: radii.circle,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: colors.primaryCyan,
    ...shadows.subtle,
  },
  nameBlock: {
    marginLeft: 12,
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  shopName: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.navy,
    maxWidth: '85%',
  },
  shopSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 1,
  },
  searchIconButton: {
    width: 38,
    height: 38,
    borderRadius: radii.circle,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 46, 110, 0.4)',
    justifyContent: 'center',
    padding: 20,
  },
  modalSheet: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    padding: 20,
    ...shadows.medium,
  },
  modalHeading: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.navy,
  },
  modalSub: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: 16,
  },
  personaOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: radii.cardSmall,
    borderWidth: 1.5,
    borderColor: colors.border,
    marginBottom: 10,
  },
  personaOptionActive: {
    borderColor: colors.primaryCyan,
    backgroundColor: colors.paleBlue,
  },
  optionAvatar: {
    width: 38,
    height: 38,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionAvatarActive: {
    backgroundColor: colors.navy,
  },
  optionName: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textMain,
  },
  optionNameActive: {
    color: colors.navy,
  },
  optionSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 1,
  },
  closeBtn: {
    backgroundColor: colors.navy,
    paddingVertical: 12,
    borderRadius: radii.button,
    alignItems: 'center',
    marginTop: 8,
  },
  closeBtnText: {
    color: colors.textWhite,
    fontSize: 14,
    fontWeight: '700',
  },
});
