import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface InfoBannerProps {
  text: string;
}

/**
 * Reusable banner for prominent status or disclaimer text.
 */
export function InfoBanner({ text }: InfoBannerProps) {
  return (
    <View style={styles.banner}>
      <Ionicons name="information-circle-outline" size={18} color="#0f3460" style={styles.icon} />
      <Text style={styles.text}>{text}</Text>
    </View>
  );
}

/** Pill label for synthetic/mock data states, matching PRD labelling requirements. */
export function SyntheticDataPill() {
  return (
    <View style={styles.pill}>
      <Text style={styles.pillText}>⚠ SYNTHETIC DATA — not Paytm data</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#e8f0fe',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  icon: {
    marginRight: 8,
    marginTop: 1,
  },
  text: {
    flex: 1,
    fontSize: 13,
    color: '#0f3460',
    lineHeight: 18,
  },
  pill: {
    alignSelf: 'flex-start',
    backgroundColor: '#fff3cd',
    borderWidth: 1,
    borderColor: '#ffc107',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginBottom: 16,
  },
  pillText: {
    fontSize: 11,
    color: '#856404',
    fontWeight: '600',
  },
});

// Silence unused import lint warning — ScrollView is exported for convenience
export { ScrollView };

