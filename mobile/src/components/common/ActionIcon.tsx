import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, spacing } from '@/theme/theme';

interface ActionIconProps {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  sublabel?: string;
  onPress: () => void;
  badgeCount?: number;
  variant?: 'paleBlue' | 'cyan' | 'navy';
}

export const ActionIcon: React.FC<ActionIconProps> = ({
  icon,
  label,
  sublabel,
  onPress,
  badgeCount,
  variant = 'paleBlue',
}) => {
  return (
    <TouchableOpacity
      style={styles.container}
      onPress={onPress}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <View
        style={[
          styles.circle,
          variant === 'cyan' && styles.circleCyan,
          variant === 'navy' && styles.circleNavy,
        ]}
      >
        <Ionicons
          name={icon}
          size={24}
          color={variant === 'paleBlue' ? colors.navy : colors.textWhite}
        />
        {typeof badgeCount === 'number' && badgeCount > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{badgeCount > 9 ? '9+' : badgeCount}</Text>
          </View>
        )}
      </View>
      <Text style={styles.label} numberOfLines={2}>
        {label}
      </Text>
      {sublabel && (
        <Text style={styles.sublabel} numberOfLines={1}>
          {sublabel}
        </Text>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    flex: 1,
    minWidth: 64,
    marginVertical: 6,
  },
  circle: {
    width: 52,
    height: 52,
    borderRadius: radii.circle,
    backgroundColor: colors.paleBlue,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#D4EEFB',
    marginBottom: 6,
    position: 'relative',
  },
  circleCyan: {
    backgroundColor: colors.primaryCyan,
    borderColor: colors.deepCyan,
  },
  circleNavy: {
    backgroundColor: colors.navy,
    borderColor: '#001E4D',
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textMain,
    textAlign: 'center',
    lineHeight: 15,
  },
  sublabel: {
    fontSize: 10,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 1,
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    backgroundColor: colors.error,
    borderRadius: radii.pill,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: colors.surface,
  },
  badgeText: {
    color: colors.textWhite,
    fontSize: 9,
    fontWeight: '800',
  },
});

