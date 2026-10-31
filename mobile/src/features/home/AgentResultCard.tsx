/**
 * Shows one agent turn: an answer, a reviewable proposal (Confirm / Cancel), or a question with choices.
 * Nothing here writes on its own; Confirm calls the atomic backend confirm.
 */
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import type { AgentTurnResult } from '@/api/ledgerClient';

function rupees(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return '—';
  return `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: paise % 100 ? 2 : 0, maximumFractionDigits: 2 })}`;
}

const KIND_LABEL: Record<string, string> = {
  customer_create: 'New customer',
  credit: 'Udhaar (credit)',
  repayment: 'Jama (repayment)',
  sale: 'Sale',
};

interface Props {
  result: AgentTurnResult;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onChoose: (slotId: string, optionId: string) => void;
}

export default function AgentResultCard({ result, busy, onConfirm, onCancel, onChoose }: Props) {
  const { transcript, proposal, clarification, answer } = result;
  const showTranscript = transcript.original && transcript.original !== transcript.used;
  return (
    <View style={styles.card} testID="agent-result">
      <View style={styles.header}>
        <Text style={styles.title}>
          {result.status === 'proposal' ? 'Review before saving' : result.status === 'clarification' ? 'One question' : 'Munim'}
        </Text>
        <Text style={[styles.badge, result.status === 'proposal' ? styles.badgeWarn : styles.badgeInfo]}>
          {result.status === 'proposal' ? 'NOT SAVED YET' : result.status === 'answer' ? 'READ ONLY' : 'NOTHING SAVED'}
        </Text>
      </View>

      {showTranscript && <Text style={styles.meta}>Heard: “{transcript.original}” · Sent: “{transcript.used}”</Text>}
      {transcript.model_corrected && (
        <Text style={styles.meta}>Understood as: “{transcript.model_corrected}” (edit the text if this is wrong)</Text>
      )}

      {result.status !== 'proposal' && <Text style={styles.message}>{result.reply_text || result.message}</Text>}

      {answer?.kind === 'balance' && (
        <Text style={styles.big}>{answer.customer_name}: {rupees(answer.balance_due_paise)} due</Text>
      )}
      {answer?.kind === 'stock_check' && (
        <Text style={styles.big}>{answer.product_name}: {answer.on_hand_quantity} {answer.unit}</Text>
      )}
      {answer?.notes?.map((note) => <Text key={note} style={styles.inferred}>Inferred · {note}</Text>)}

      {proposal && (
        <View>
          {proposal.actions.map((action) => (
            <View key={action.index} style={styles.action}>
              <Text style={styles.actionKind}>{KIND_LABEL[action.kind] ?? action.kind}</Text>
              <Text style={styles.actionText}>{action.summary}</Text>
              {action.inferred.map((note) => <Text key={note} style={styles.inferred}>Inferred · {note}</Text>)}
            </View>
          ))}
          <Text style={styles.meta}>
            {proposal.actions.length > 1 ? 'All of these are saved together, or none are. ' : ''}
            Nothing is saved until you tap Confirm.
          </Text>
          <View style={styles.row}>
            <TouchableOpacity style={styles.cancel} onPress={onCancel} disabled={busy}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.confirm, busy && styles.disabled]} onPress={onConfirm} disabled={busy} testID="agent-confirm">
              <Text style={styles.confirmText}>Confirm and save</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {clarification?.slot_id && clarification.choices.length > 0 && (
        <View>
          {clarification.choices.map((choice) => (
            <TouchableOpacity
              key={choice.option_id}
              style={styles.choice}
              onPress={() => onChoose(clarification.slot_id as string, choice.option_id)}
              disabled={busy}
            >
              <Text style={styles.choiceLabel}>{choice.label}</Text>
              {choice.detail ? <Text style={styles.choiceDetail}>{choice.detail}</Text> : null}
            </TouchableOpacity>
          ))}
        </View>
      )}
      {clarification && <Text style={styles.meta}>You can also just say or type the missing detail.</Text>}

      <Text style={styles.footer}>
        {result.interpreted_by === 'gemini' ? 'Understood with Gemini' : result.interpreted_by === 'deterministic' ? 'Understood offline (rules)' : 'From your choice / previous request'}
        {result.reply_worded_by === 'gemini' ? ' · Reply worded by Gemini from verified figures' : ''}
        {result.llm.status !== 'ok' && result.llm.status !== 'disabled' && result.llm.detail ? ` · Gemini: ${result.llm.detail}` : ''}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#ffffff', borderRadius: 12, padding: 14, marginVertical: 8, borderWidth: 1, borderColor: '#dbe4f0' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  title: { fontSize: 15, fontWeight: '700', color: '#0f3460' },
  badge: { fontSize: 10, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, overflow: 'hidden' },
  badgeWarn: { backgroundColor: '#fff3cd', color: '#856404' },
  badgeInfo: { backgroundColor: '#e7f1ff', color: '#0f3460' },
  meta: { fontSize: 12, color: '#6c757d', marginTop: 4 },
  message: { fontSize: 14, color: '#212529', marginTop: 4 },
  big: { fontSize: 18, fontWeight: '700', color: '#212529', marginTop: 6 },
  action: { borderLeftWidth: 3, borderLeftColor: '#0f3460', paddingLeft: 10, marginTop: 8 },
  actionKind: { fontSize: 12, fontWeight: '700', color: '#0f3460', textTransform: 'uppercase' },
  actionText: { fontSize: 14, color: '#212529', marginTop: 2 },
  inferred: { fontSize: 12, color: '#8a5a00', marginTop: 3 },
  row: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 12, gap: 10 },
  cancel: { paddingVertical: 10, paddingHorizontal: 16, borderRadius: 8, borderWidth: 1, borderColor: '#ced4da' },
  cancelText: { color: '#495057', fontWeight: '600' },
  confirm: { paddingVertical: 10, paddingHorizontal: 16, borderRadius: 8, backgroundColor: '#0f3460' },
  confirmText: { color: '#ffffff', fontWeight: '700' },
  disabled: { opacity: 0.5 },
  choice: { borderWidth: 1, borderColor: '#0f3460', borderRadius: 8, padding: 10, marginTop: 8 },
  choiceLabel: { fontSize: 14, fontWeight: '600', color: '#0f3460' },
  choiceDetail: { fontSize: 12, color: '#6c757d', marginTop: 2 },
  footer: { fontSize: 11, color: '#adb5bd', marginTop: 10 },
});
