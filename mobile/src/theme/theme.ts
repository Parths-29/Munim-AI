/**
 * Munim-AI Visual Design System
 * Paytm-inspired Merchant Palette & Styling Standards
 */

export const colors = {
  // Brand colors
  primaryCyan: '#00BAF2',
  deepCyan: '#0099D8',
  navy: '#002E6E',
  paleBlue: '#E8F7FD',

  // Surfaces & Backgrounds
  background: '#F2F4F8',
  surface: '#FFFFFF',
  surfaceSubtle: '#F8FAFC',
  headerPaleBlue: '#E8F7FD',

  // Text
  textMain: '#17212B',
  textSecondary: '#5A6B7B',
  textMuted: '#8E9BA8',
  textNavy: '#002E6E',
  textWhite: '#FFFFFF',

  // Dividers & Borders
  border: '#E4EAF0',
  borderFocus: '#00BAF2',
  borderSubtle: '#EDF2F7',

  // Semantic Status
  success: '#2FA84F',
  successSurface: '#EAF8EE',
  warning: '#B77912',
  warningSurface: '#FEF3C7',
  error: '#D9363E',
  errorSurface: '#FDE8E9',

  // Specific Fintech Accents
  udhaarRed: '#D9363E',
  jamaGreen: '#2FA84F',
  badgeDemo: '#002E6E',
  badgeDemoBg: '#E8F7FD',
  simulatedBg: '#FFFBEB',
  simulatedText: '#92400E',
};

export const typography = {
  fontFamily: {
    regular: 'System',
    medium: 'System',
    bold: 'System',
  },
  fontSize: {
    heroAmount: 32,
    largeAmount: 28,
    heading: 20,
    subheading: 17,
    body: 15,
    bodySmall: 13,
    caption: 11,
    micro: 10,
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  screenPadding: 16,
};

export const radii = {
  card: 18,
  cardSmall: 14,
  input: 14,
  button: 14,
  pill: 999,
  circle: 999,
};

export const shadows = {
  subtle: {
    shadowColor: '#002E6E',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  medium: {
    shadowColor: '#002E6E',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  cyanGlow: {
    shadowColor: '#00BAF2',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 6,
  },
};

