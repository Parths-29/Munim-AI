// Run with `npm test` (Node's built-in test runner; no extra dependencies).
// The TypeScript parser is transpiled in memory with the project's own TypeScript compiler.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { before, describe, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

let parse;
let uncertainNumberWords;

before(async () => {
  const source = fs.readFileSync(fileURLToPath(new URL('../src/features/home/parseMerchantCommand.ts', import.meta.url)), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'munim-parser-')), 'parseMerchantCommand.mjs');
  fs.writeFileSync(file, outputText);
  ({ parseMerchantCommand: parse, uncertainNumberWords } = await import(pathToFileURL(file).href));
});

const ready = (utterance, intent, customerQuery, amountPaise) =>
  assert.deepEqual(parse(utterance), { status: 'ready', intent, customerQuery, amountPaise }, utterance);

describe('reported case: "pachs add kro"', () => {
  test('asks for customer, action, and amount without guessing', () => {
    const result = parse('pachs add kro');
    assert.equal(result.status, 'clarification');
    assert.match(result.message, /which customer/);
    assert.match(result.message, /udhaar \(credit given\) or jama \(payment received\)/);
    assert.match(result.message, /amount in rupees/);
    assert.match(result.message, /“pachs” might be a number \(pachis = 25 or pachas = 50\), so I did not use it as an amount/);
    assert.match(result.message, /do not carry the customer over/);
  });

  test('"pachs" is reported as uncertain, not converted', () => {
    assert.deepEqual(uncertainNumberWords('pachs add kro').map((item) => item.word), ['pachs']);
    assert.deepEqual(uncertainNumberWords('Raju ko udhaar add karo'), []);
  });
});

describe('natural Hinglish credit/repayment with exact customer, action, and rupee amount', () => {
  test('verbs and fillers never leak into the customer name', () => {
    ready('Raju ko pachaas rupaye udhaar add karo', 'credit', 'Raju', 5000);
    ready('Raju ko pachaas rupaye udhaar add kro', 'credit', 'Raju', 5000);
    ready('Raju ke 50 rupaye udhaar kardo', 'credit', 'Raju', 5000);
    ready('Raju ke naam par 1,250 rupees ka udhaar note karo', 'credit', 'Raju', 125000);
    ready('Raju ne pachaas rupaye jama kiye', 'repayment', 'Raju', 5000);
    ready('Raju bhai ka ₹50 udhaar likh do', 'credit', 'Raju bhai', 5000);
  });

  test('"udhar" spelling is credit', () => {
    ready('Raju ka 50 rupaye udhar likho', 'credit', 'Raju', 5000);
  });
});

describe('specific follow-ups instead of guesses', () => {
  test('generic "add" with an amount but no udhaar/jama asks which one', () => {
    const result = parse('Raju ko 50 rupaye add karo');
    assert.equal(result.status, 'clarification');
    assert.match(result.message, /^Please tell me whether it is udhaar \(credit given\) or jama \(payment received\)\./);
  });

  test('missing amount', () => {
    const result = parse('Raju ko udhaar add karo');
    assert.equal(result.status, 'clarification');
    assert.match(result.message, /^Please tell me the amount in rupees\./);
  });

  test('missing customer never becomes a customer called "karo"', () => {
    const result = parse('50 rupaye udhaar add karo');
    assert.equal(result.status, 'clarification');
    assert.match(result.message, /^Please tell me which customer it is for\./);
  });

  test('a quantity is not rupees', () => {
    const result = parse('Raju ko 2 packet udhaar');
    assert.equal(result.status, 'clarification');
    assert.match(result.message, /“2 packet” is a quantity, not rupees/);
  });

  test('two amounts and two actions still stop', () => {
    assert.equal(parse('Raju ko 50 ya 500 rupaye udhaar').status, 'clarification');
    assert.equal(parse('Raju ka 50 rupaye udhaar aur jama').status, 'clarification');
  });
});

describe('existing commands unchanged', () => {
  test('balance, stock, customer create, summaries', () => {
    assert.deepEqual(parse('Raju bhai ka balance batao'), { status: 'ready', intent: 'balance', customerQuery: 'Raju bhai' });
    assert.deepEqual(parse('Maggi khatam ho gaya'), { status: 'ready', intent: 'stockout', productQuery: 'Maggi' });
    assert.deepEqual(parse('Add new customer Rajju Sharma'), { status: 'ready', intent: 'customer_create', customerName: 'Rajju Sharma' });
    assert.deepEqual(parse('set Maggi stock count to 10 packs'), { status: 'ready', intent: 'stock_count', productQuery: 'Maggi', countedQuantity: 10 });
    assert.deepEqual(parse('What happened in the shop today?'), { status: 'ready', intent: 'timeline_summary' });
  });

  test('phrases the parser does not own still go to Sarvam (unsupported)', () => {
    assert.equal(parse('Meena ne ₹75 wapas diye').status, 'unsupported');
  });
});
