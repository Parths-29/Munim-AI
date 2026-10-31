import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { colors, radii, shadows } from '@/theme/theme';

interface PaytmCardProps {
  children: React.ReactNode;
  style?: ViewStyle | ViewStyle[];
  variant?: 'default' | 'outlined' | 'elevated' | 'paleBlue';
}

export const PaytmCard: React.FC<PaytmCardProps> = ({
  children,
  style,
  variant = 'default',
}) => {
  return (
    <View
      style={[
        styles.base,
        variant === 'outlined' && styles.outlined,
        variant === 'elevated' && styles.elevated,
        variant === 'paleBlue' && styles.paleBlue,
        style,
      ]}
    >
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    ...shadows.subtle,
  },
  outlined: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1.5,
    borderColor: colors.border,
    padding: 16,
    elevation: 0,
    shadowOpacity: 0,
  },
  elevated: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    ...shadows.medium,
  },
  paleBlue: {
    backgroundColor: colors.paleBlue,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: '#CBEBFA',
    padding: 16,
  },
});

