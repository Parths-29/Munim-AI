// Encodes upload parts with Expo's own native FormData encoder (node_modules/expo, expo/fetch)
// to reproduce "Unsupported FormDataPart implementation" and prove the fix.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'munim-upload-'));
let convertFormDataAsync;
let nativeUploadPart;

async function load(relativeSource, outName, patch = (code) => code) {
  const source = fs.readFileSync(fileURLToPath(new URL(relativeSource, import.meta.url)), 'utf8');
  const { outputText } = ts.transpileModule(patch(source), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  const file = path.join(dir, outName);
  fs.writeFileSync(file, outputText);
  return import(pathToFileURL(file).href);
}

before(async () => {
  ({ convertFormDataAsync } = await load(
    '../node_modules/expo/src/winter/fetch/convertFormData.ts',
    'convertFormData.mjs',
    (code) => code
      .replace(/^import \{ blobToArrayBufferAsync \}.*$/m, 'const blobToArrayBufferAsync = async (blob: Blob) => blob.arrayBuffer();')
      .replace(/^import type .*$/m, 'type ExpoFormDataValue = any;'),
  ));
  ({ nativeUploadPart } = await load('../src/api/nativeUploadPart.ts', 'nativeUploadPart.mjs'));
});

const formWith = (part) => ({ entries: () => [['file', part]] });
const decode = (bytes) => Buffer.from(bytes).toString('latin1');

test('old React Native { uri, name, type } part fails in expo/fetch (the phone error)', async () => {
  const oldPart = { uri: 'file:///data/user/0/app/cache/recording.m4a', name: 'merchant-voice.m4a', type: 'audio/mp4' };
  await assert.rejects(convertFormDataAsync(formWith(oldPart), 'BOUNDARY'), /Unsupported FormDataPart implementation/);
});

test('new part encodes with filename, audio/mp4 type, and the recorded bytes', async () => {
  const audio = new Uint8Array([0, 0, 0, 24, 102, 116, 121, 112, 77, 52, 65, 32]); // "....ftypM4A "
  const part = nativeUploadPart('file:///cache/recording.m4a', 'merchant-voice.m4a', 'audio/mp4', async () => audio);
  const { body, boundary } = await convertFormDataAsync(formWith(part), 'BOUNDARY');
  const text = decode(body);
  assert.equal(boundary, 'BOUNDARY');
  assert.match(text, /content-disposition: form-data; name="file"; filename="merchant-voice\.m4a"\r\n/);
  assert.match(text, /content-type: audio\/mp4\r\n\r\n/);
  assert.ok(text.includes(decode(audio)), 'recorded bytes are in the body');
  assert.ok(text.endsWith('--BOUNDARY--\r\n'));
});

test('new part still carries uri for React Native fetch (EXPO_PUBLIC_USE_RN_FETCH=1)', () => {
  const part = nativeUploadPart('file:///cache/recording.m4a', 'merchant-voice.m4a', 'audio/mp4', async () => new Uint8Array());
  assert.equal(part.uri, 'file:///cache/recording.m4a');
});
