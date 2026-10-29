/**
 * Shared type definitions for the mobile scaffold.
 *
 * These mirror the v1 contracts in docs/contracts/ but contain
 * only the shapes needed for the Phase 1 UI shell.
 * No business logic is implemented here.
 */

/** Intents defined in docs/contracts/command-proposal.schema.json */
export type CommandIntent =
  | 'create_credit'
  | 'record_repayment'
  | 'get_customer_balance'
  | 'report_stockout'
  | 'adjust_stock'
  | 'get_daily_summary';

/** Status values for a typed command proposal */
export type CommandStatus = 'READY' | 'NEEDS_CLARIFICATION';

/**
 * A lightweight reference to command-proposal.schema.json.
 * The backend validates and authorises proposals; the UI only displays them.
 */
export interface CommandProposal {
  schema_version: '1.0';
  command_id: string;
  shop_id: string;
  intent: CommandIntent;
  status: CommandStatus;
  confidence: number;
  requires_merchant_confirmation: boolean;
  clarification_question?: string | null;
}

/** Channel for input — text only in Phase 1 */
export type InputChannel = 'text';

