/**
 * Multipart file part for Android/iOS uploads.
 *
 * Expo SDK 58 installs `expo/fetch` as the global `fetch` on native. Its FormData encoder reads file
 * bytes through a `bytes()` method and rejects React Native's bare `{ uri, name, type }` descriptor
 * with "Unsupported FormDataPart implementation". React Native's own fetch (used when
 * EXPO_PUBLIC_USE_RN_FETCH=1) needs `uri` instead. This part carries both, so either fetch works.
 */
export interface NativeUploadPart {
  uri: string;
  name: string;
  type: string;
  bytes: () => Promise<Uint8Array>;
}

export function nativeUploadPart(
  uri: string,
  name: string,
  type: string,
  readBytes: () => Promise<Uint8Array>,
): NativeUploadPart {
  return { uri, name, type, bytes: readBytes };
}
