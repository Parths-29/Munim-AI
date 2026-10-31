import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, shadows } from '@/theme/theme';

export type NavTab = 'home' | 'khata' | 'munim' | 'stock' | 'more';

interface BottomNavProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  onPressMunim: () => void;
  reviewCount?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  activeTab,
  onSelectTab,
  onPressMunim,
  reviewCount = 0,
}) => {
  return (
    <View style={styles.navWrapper}>
      <View style={styles.container}>
        {/* Tab 1: Home */}
        <TouchableOpacity
          style={styles.tabButton}
          onPress={() => onSelectTab('home')}
          activeOpacity={0.7}
          accessibilityRole="tab"
          accessibilityLabel="Home"
        >
          <Ionicons
            name={activeTab === 'home' ? 'home' : 'home-outline'}
            size={22}
            color={activeTab === 'home' ? colors.primaryCyan : colors.textSecondary}
          />
          <Text style={[styles.tabLabel, activeTab === 'home' && styles.tabLabelActive]}>
            Home
          </Text>
        </TouchableOpacity>

        {/* Tab 2: Khata */}
        <TouchableOpacity
          style={styles.tabButton}
          onPress={() => onSelectTab('khata')}
          activeOpacity={0.7}
          accessibilityRole="tab"
          accessibilityLabel="Customer Khata"
        >
          <Ionicons
            name={activeTab === 'khata' ? 'book' : 'book-outline'}
            size={22}
            color={activeTab === 'khata' ? colors.primaryCyan : colors.textSecondary}
          />
          <Text style={[styles.tabLabel, activeTab === 'khata' && styles.tabLabelActive]}>
            Khata
          </Text>
        </TouchableOpacity>

        {/* Tab 3: Center MUNIM Voice Assistant Button */}
        <View style={styles.centerButtonContainer}>
          <TouchableOpacity
            style={styles.munimCircle}
            onPress={onPressMunim}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Speak to Munim AI Copilot"
          >
            <View style={styles.micInner}>
              <Ionicons name="mic" size={26} color={colors.navy} />
            </View>
          </TouchableOpacity>
          <Text style={styles.munimLabel}>Bolo Munim</Text>
        </View>

        {/* Tab 4: Stock */}
        <TouchableOpacity
          style={styles.tabButton}
          onPress={() => onSelectTab('stock')}
          activeOpacity={0.7}
          accessibilityRole="tab"
          accessibilityLabel="Inventory and Stock"
        >
          <Ionicons
            name={activeTab === 'stock' ? 'cube' : 'cube-outline'}
            size={22}
            color={activeTab === 'stock' ? colors.primaryCyan : colors.textSecondary}
          />
          <Text style={[styles.tabLabel, activeTab === 'stock' && styles.tabLabelActive]}>
            Stock
          </Text>
        </TouchableOpacity>

        {/* Tab 5: More */}
        <TouchableOpacity
          style={styles.tabButton}
          onPress={() => onSelectTab('more')}
          activeOpacity={0.7}
          accessibilityRole="tab"
          accessibilityLabel="More options"
        >
          <View style={{ position: 'relative' }}>
            <Ionicons
              name={activeTab === 'more' ? 'grid' : 'grid-outline'}
              size={22}
              color={activeTab === 'more' ? colors.primaryCyan : colors.textSecondary}
            />
            {reviewCount > 0 && (
              <View style={styles.badgeDot} />
            )}
          </View>
          <Text style={[styles.tabLabel, activeTab === 'more' && styles.tabLabelActive]}>
            More
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  navWrapper: {
    backgroundColor: 'transparent',
  },
  container: {
    flexDirection: 'row',
    height: 64,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingHorizontal: 8,
    alignItems: 'center',
    justifyContent: 'space-between',
    ...shadows.medium,
  },
  tabButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    minWidth: 44,
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: 3,
  },
  tabLabelActive: {
    color: colors.navy,
    fontWeight: '800',
  },
  centerButtonContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'flex-start',
    marginTop: -22,
  },
  munimCircle: {
    width: 54,
    height: 54,
    borderRadius: radii.circle,
    backgroundColor: colors.primaryCyan,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: colors.surface,
    ...shadows.cyanGlow,
  },
  micInner: {
    width: 44,
    height: 44,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  munimLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.navy,
    marginTop: 3,
  },
  badgeDot: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.error,
  },
});

