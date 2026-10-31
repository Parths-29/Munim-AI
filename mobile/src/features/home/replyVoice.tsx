/**
 * Spoken replies: fetch Sarvam audio for text the app already shows, play it, allow replay/stop.
 * Native playback uses a temporary cache file that is deleted when playback ends or stops; nothing is kept.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AudioPlayer, createAudioPlayer, setAudioModeAsync } from 'expo-audio';
import { File, Paths } from 'expo-file-system';

import { agentSpeak } from '@/api/ledgerClient';

export type ReplyVoiceState = 'idle' | 'loading' | 'playing' | 'error';

export function useReplyVoice() {
  const playerRef = useRef<AudioPlayer | null>(null);
  const fileRef = useRef<File | null>(null);
  const requestRef = useRef(0);
  const [last, setLast] = useState<{ text: string; language: string } | null>(null);
  const [state, setState] = useState<ReplyVoiceState>('idle');
  const [error, setError] = useState<string | null>(null);

  const release = useCallback(() => {
    try {
      playerRef.current?.pause();
      playerRef.current?.remove();
    } catch {
      // player already released
    }
    playerRef.current = null;
    try {
      if (fileRef.current?.exists) fileRef.current.delete();
    } catch {
      // temp file already gone
    }
    fileRef.current = null;
  }, []);

  useEffect(() => release, [release]);

  const speak = useCallback(async (text: string, language: string) => {
    const requestId = ++requestRef.current;
    release();
    setLast({ text, language });
    setError(null);
    setState('loading');
    try {
      const audio = await agentSpeak(text, language);
      if (requestId !== requestRef.current) return; // a newer reply replaced this one
      let uri: string;
      if (Platform.OS === 'web') {
        uri = `data:${audio.mime_type};base64,${audio.audio_base64}`;
      } else {
        const file = new File(Paths.cache, `munim-reply-${Date.now()}.wav`);
        file.create({ overwrite: true });
        file.write(audio.audio_base64, { encoding: 'base64' });
        fileRef.current = file;
        uri = file.uri;
        await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      }
      const player = createAudioPlayer({ uri });
      playerRef.current = player;
      player.addListener('playbackStatusUpdate', (status) => {
        if (status.didJustFinish && requestId === requestRef.current) {
          release();
          setState('idle');
        }
      });
      player.play();
      setState('playing');
    } catch (err: unknown) {
      if (requestId !== requestRef.current) return;
      release();
      setState('error');
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [release]);

  const stop = useCallback(() => {
    requestRef.current += 1;
    release();
    setState('idle');
  }, [release]);

  const replay = useCallback(() => {
    if (last) void speak(last.text, last.language);
  }, [last, speak]);

  return { state, error, last, speak, stop, replay };
}

interface BarProps {
  voice: ReturnType<typeof useReplyVoice>;
  enabled: boolean;
  onToggle: () => void;
}

export function ReplyVoiceBar({ voice, enabled, onToggle }: BarProps) {
  return (
    <View style={styles.bar} testID="reply-voice-bar">
      <TouchableOpacity onPress={onToggle} style={styles.toggle} accessibilityLabel={enabled ? 'Turn spoken replies off' : 'Turn spoken replies on'}>
        <Ionicons name={enabled ? 'volume-high' : 'volume-mute'} size={16} color="#0f3460" />
        <Text style={styles.toggleText}>{enabled ? 'Spoken replies on' : 'Spoken replies off'}</Text>
      </TouchableOpacity>
      {voice.state === 'loading' && <Text style={styles.status}>Preparing voice…</Text>}
      {voice.state === 'playing' && (
        <TouchableOpacity onPress={voice.stop} style={styles.button} accessibilityLabel="Stop spoken reply">
          <Ionicons name="stop" size={14} color="#ffffff" />
          <Text style={styles.buttonText}>Stop</Text>
        </TouchableOpacity>
      )}
      {(voice.state === 'idle' || voice.state === 'error') && voice.last && (
        <TouchableOpacity onPress={voice.replay} style={styles.button} accessibilityLabel="Replay spoken reply">
          <Ionicons name="play" size={14} color="#ffffff" />
          <Text style={styles.buttonText}>Replay</Text>
        </TouchableOpacity>
      )}
      {voice.state === 'error' && voice.error && <Text style={styles.error}>Voice reply unavailable: {voice.error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginVertical: 4 },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4 },
  toggleText: { fontSize: 12, color: '#0f3460', fontWeight: '600' },
  status: { fontSize: 12, color: '#6c757d' },
  button: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#0f3460', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14 },
  buttonText: { color: '#ffffff', fontSize: 12, fontWeight: '600' },
  error: { fontSize: 12, color: '#b02a37', flexBasis: '100%' },
});
