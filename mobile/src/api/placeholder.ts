/**
 * api/placeholder.ts
 *
 * Phase 1 stub — no real network calls are made.
 * Replace with actual fetch() calls in Phase 2 once the backend
 * endpoints defined in backend/app/api/ are ready.
 */

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Placeholder for the future POST /commands endpoint.
 * Returns null in Phase 1; will return CommandProposal in Phase 2.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function submitTextCommand(_utterance: string): Promise<null> {
  // TODO(phase-2): POST { utterance } to `${API_BASE_URL}/commands`
  return null;
}

