// The transcription/agent calls must fail clearly instead of spinning forever.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

let mod;
let server;
let port;

before(async () => {
  const source = fs.readFileSync(fileURLToPath(new URL('../src/api/http.ts', import.meta.url)), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'munim-http-')), 'http.mjs');
  fs.writeFileSync(file, outputText);
  mod = await import(pathToFileURL(file).href);
  server = http.createServer(() => { /* never answers: simulates a stuck transcription */ });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  port = server.address().port;
});

after(() => { server.closeAllConnections?.(); server.close(); });

test('a hung request times out with a clear message', async () => {
  const started = Date.now();
  await assert.rejects(
    mod.fetchWithTimeout(`http://127.0.0.1:${port}/speech/transcribe`, { method: 'POST' }, 300, 'Transcription', 'http://192.168.1.42:8000'),
    (err) => err instanceof mod.NetworkTimeoutError && /Transcription took longer than 0 seconds/.test(err.message) && /192\.168\.1\.42:8000/.test(err.message),
  );
  assert.ok(Date.now() - started < 3000);
});

test('an unreachable backend explains the phone setup', async () => {
  await assert.rejects(
    mod.fetchWithTimeout('http://127.0.0.1:9/agent/turn', { method: 'POST' }, 5000, 'Understanding the request', 'http://127.0.0.1:8000'),
    (err) => err instanceof mod.BackendUnreachableError && /--host 0\.0\.0\.0/.test(err.message),
  );
});
