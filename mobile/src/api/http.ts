/** Bounded network calls: a spinner must never wait forever. No React Native imports (unit-tested in Node). */
export class NetworkTimeoutError extends Error {}
export class BackendUnreachableError extends Error {}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
  label: string,
  baseUrl: string,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err: unknown) {
    if (controller.signal.aborted) {
      throw new NetworkTimeoutError(
        `${label} took longer than ${Math.round(timeoutMs / 1000)} seconds. Check that the backend at ${baseUrl} is reachable from this device, then try again.`,
      );
    }
    const detail = err instanceof Error ? err.message : String(err);
    throw new BackendUnreachableError(
      `Could not reach the backend at ${baseUrl} (${detail}). On a phone, set EXPO_PUBLIC_API_BASE_URL to the laptop's LAN IP and run the backend with --host 0.0.0.0.`,
    );
  } finally {
    clearTimeout(timer);
  }
}
