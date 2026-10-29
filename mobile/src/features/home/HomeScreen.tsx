/**
 * HomeScreen — Phase 1 scaffold
 *
 * This is the main entry point for Munim-AI on Android (Expo Go).
 *
 * Phase 1 scope:
 *  - Text input box for the merchant to type a command
 *  - Static example prompts shown as quick-tap chips
 *  - Clear notice that voice and business actions are NOT implemented yet
 *  - Synthetic-data banner (required by PRD for all demo screens)
 *
 * NOT in Phase 1 (and therefore NOT present here):
 *  - Microphone / speech permissions or libraries
 *  - LLM / Sarvam STT-TTS integration
 *  - Ledger, credit, repayment, or stock logic
 *  - Payment reconciliation or analytics
 *  - Database reads or writes
 *  - Backend API calls (see src/api/placeholder.ts for the stub)
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { InfoBanner, SyntheticDataPill } from '@/components/InfoBanner';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HistoryEntry {
  id: string;
  text: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Example prompts from the PRD demo flow; not wired to any backend in Phase 1. */
const EXAMPLE_PROMPTS: string[] = [
  'Raju bhai ka ₹50 udhaar likh do',
  'Maggi khatam ho gaya',
  'Raju bhai ka balance batao',
  'Aaj kaisa raha?',
];

const PHASE_1_NOTICE =
  'Phase 1 scaffold only. Voice input, business commands, ledger,' +
  ' payment reconciliation, and AI responses are not implemented yet.' +
  ' Text you type is logged locally and not sent to any server.';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function HomeScreen() {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed) return;

    const entry: HistoryEntry = {
      id: `local-${Date.now()}`,
      text: trimmed,
      timestamp: new Date().toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    };
    setHistory((prev) => [entry, ...prev]);
    setInput('');
  }, [input]);

  const handlePromptChip = useCallback((prompt: string) => {
    setInput(prompt);
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={88}
      >
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* ── Header ──────────────────────────────────────────────────── */}
          <View style={styles.header}>
            <Text style={styles.appName}>Munim-AI</Text>
            <Text style={styles.tagline}>Voice-first shop copilot · KiranaOS</Text>
          </View>

          <SyntheticDataPill />

          {/* ── Phase 1 notice ──────────────────────────────────────────── */}
          <InfoBanner text={PHASE_1_NOTICE} />

          {/* ── No microphone notice ──────────────────────────────────── */}
          <View style={styles.noMicRow}>
            <Ionicons name="mic-off-outline" size={16} color="#dc3545" />
            <Text style={styles.noMicText}>
              Voice / microphone not available in Phase 1
            </Text>
          </View>

          {/* ── Example prompts ──────────────────────────────────────────── */}
          <Text style={styles.sectionLabel}>Example commands (tap to fill)</Text>
          <View style={styles.chipRow}>
            {EXAMPLE_PROMPTS.map((prompt) => (
              <TouchableOpacity
                key={prompt}
                style={styles.chip}
                onPress={() => handlePromptChip(prompt)}
                accessibilityRole="button"
                accessibilityLabel={`Fill example: ${prompt}`}
              >
                <Text style={styles.chipText}>{prompt}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* ── Local history ────────────────────────────────────────────── */}
          {history.length > 0 && (
            <>
              <Text style={styles.sectionLabel}>Local input log (not sent anywhere)</Text>
              {history.map((entry) => (
                <View key={entry.id} style={styles.historyCard}>
                  <Text style={styles.historyText}>{entry.text}</Text>
                  <Text style={styles.historyTime}>{entry.timestamp}</Text>
                </View>
              ))}
            </>
          )}
        </ScrollView>

        {/* ── Input bar (pinned to bottom) ─────────────────────────────── */}
        <View style={styles.inputBar}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="Type a command in Hindi or English…"
            placeholderTextColor="#9aa0a6"
            returnKeyType="send"
            onSubmitEditing={handleSubmit}
            accessibilityLabel="Command input"
          />
          <TouchableOpacity
            style={[styles.sendBtn, !input.trim() && styles.sendBtnDisabled]}
            onPress={handleSubmit}
            disabled={!input.trim()}
            accessibilityRole="button"
            accessibilityLabel="Submit command"
          >
            <Ionicons name="send" size={20} color="#ffffff" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  flex: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 8,
  },

  // ── Header
  header: {
    marginBottom: 16,
  },
  appName: {
    fontSize: 28,
    fontWeight: '800',
    color: '#0f3460',
  },
  tagline: {
    fontSize: 13,
    color: '#6c757d',
    marginTop: 2,
  },

  // ── No-mic notice
  noMicRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  noMicText: {
    fontSize: 13,
    color: '#dc3545',
    marginLeft: 6,
  },

  // ── Section labels
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6c757d',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },

  // ── Example prompt chips
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 20,
  },
  chip: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#0f3460',
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipText: {
    fontSize: 13,
    color: '#0f3460',
  },

  // ── History cards
  historyCard: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    borderLeftWidth: 3,
    borderLeftColor: '#0f3460',
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  historyText: {
    flex: 1,
    fontSize: 14,
    color: '#212529',
  },
  historyTime: {
    fontSize: 11,
    color: '#9aa0a6',
    marginLeft: 8,
  },

  // ── Input bar
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#dee2e6',
    backgroundColor: '#ffffff',
  },
  textInput: {
    flex: 1,
    height: 44,
    backgroundColor: '#f8f9fa',
    borderRadius: 22,
    paddingHorizontal: 16,
    fontSize: 14,
    color: '#212529',
    borderWidth: 1,
    borderColor: '#dee2e6',
    marginRight: 8,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#0f3460',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: '#adb5bd',
  },
});

