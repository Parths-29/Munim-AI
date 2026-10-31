import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, radii } from '@/theme/theme';

export type BadgeVariant =
  | 'simulated'
  | 'demo'
  | 'success'
  | 'warning'
  | 'error'
  | 'neutral'
  | 'draft'
  | 'notSaved';

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  size?: 'small' | 'medium';
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  variant = 'neutral',
  size = 'small',
}) => {
  return (
    <View style={[styles.base, styles[variant], size === 'medium' && styles.medium]}>
      <Text style={[styles.badgeText, textStyles[variant], size === 'medium' && styles.mediumText]}>
        {label}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  base: {
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: radii.pill,
    alignSelf: 'flex-start',
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  medium: {
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  mediumText: {
    fontSize: 11,
  },
  simulated: {
    backgroundColor: colors.simulatedBg,
    borderColor: '#FCD34D',
  },
  demo: {
    backgroundColor: colors.badgeDemoBg,
    borderColor: '#BAE6FD',
  },
  success: {
    backgroundColor: colors.successSurface,
    borderColor: '#B8DFBF',
  },
  warning: {
    backgroundColor: colors.warningSurface,
    borderColor: '#FDE68A',
  },
  error: {
    backgroundColor: colors.errorSurface,
    borderColor: '#FECACA',
  },
  neutral: {
    backgroundColor: '#F1F5F9',
    borderColor: colors.border,
  },
  draft: {
    backgroundColor: '#F3E8FF',
    borderColor: '#DDD6FE',
  },
  notSaved: {
    backgroundColor: '#FFFBEB',
    borderColor: '#F59E0B',
  },
});

const textStyles = StyleSheet.create({
  simulated: {
    color: colors.simulatedText,
  },
  demo: {
    color: colors.navy,
  },
  success: {
    color: '#166534',
  },
  warning: {
    color: '#92400E',
  },
  error: {
    color: '#991B1B',
  },
  neutral: {
    color: colors.textSecondary,
    fontWeight: '600',
  },
  draft: {
    color: '#6B21A8',
  },
  notSaved: {
    color: '#92400E',
    fontWeight: '800',
  },
});
