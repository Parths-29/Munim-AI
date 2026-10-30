export type MerchantCommandIntent =
  | 'credit'
  | 'repayment'
  | 'balance'
  | 'customer_create'
  | 'stockout'
  | 'stock_check'
  | 'stock_count'
  | 'payment_summary'
  | 'timeline_summary';

export type ParsedMerchantCommand =
  | {
      status: 'ready';
      intent: 'credit' | 'repayment';
      customerQuery: string;
      amountPaise: number;
    }
  | { status: 'ready'; intent: 'balance'; customerQuery: string }
  | { status: 'ready'; intent: 'customer_create'; customerName: string }
  | { status: 'ready'; intent: 'stockout'; productQuery: string }
  | { status: 'ready'; intent: 'stock_check'; productQuery: string }
  | { status: 'ready'; intent: 'stock_count'; productQuery: string; countedQuantity: number }
  | { status: 'ready'; intent: 'payment_summary' }
  | { status: 'ready'; intent: 'timeline_summary' }
  | {
      status: 'clarification';
      message: string;
    }
  | {
      status: 'unsupported';
      message: string;
    };

const CREDIT_TERMS = /\b(?:udhaar|credit|borrowed|lend)\b/i;
const REPAYMENT_TERMS = /\b(?:jamma|jama|repay(?:ment)?|paid|received|vasool(?:i)?)\b/i;
const BALANCE_TERMS = /\b(?:balance|baki|baaki|due|owes?|outstanding)\b|kitna\s+udhaar/i;
const STOCKOUT_TERMS = /\b(?:khatam|stockout|sold\s+out|out\s+of\s+stock)\b/i;
const CUSTOMER_CREATE_TERMS = /\b(?:add|create|register)\s+(?:a\s+)?(?:new\s+)?customer\b|\bnew\s+customer\b|\bcustomer\s+(?:add|create|register)\b|\b(?:naya|nayi)\s+(?:grahak|customer)\b|\b(?:grahak|customer)\s+(?:jodo|banao|bana\s+do)\b/i;
const STOCK_COUNT_TERMS = /\b(?:physical\s+count|stock\s+count|count|counted|ginti)\b/i;
const STOCK_CHECK_TERMS = /\b(?:stock|inventory|available|remaining|left|bache|baaki\s+packs?)\b|kitne\s+(?:packs?|pieces?|bottles?)\b/i;
const PAYMENT_SUMMARY_TERMS = /\b(?:payment|payments|upi|settlement|received|collections?)\b.*\b(?:summary|today|total|status|came|got|get|getting|arrived|received|review|pending|kitne|kitna|aaye|aaya|mila)\b|\b(?:summary|total|status)\b.*\b(?:payment|payments|upi|received|collections?)\b/i;
const TIMELINE_SUMMARY_TERMS = /\b(?:activity|timeline|events?)\b.*\b(?:summary|summarize|today|recent|what happened)\b|\b(?:summarize|summary|what happened)\b.*\b(?:shop|business|activity|today)\b|\bwhat\s+(?:did\s+i|happened|was\s+recorded)\b.*\b(?:today|shop|business)\b/i;
// Keep common Indian and western thousands separators inside one amount token.
// Validation below rejects malformed grouping rather than guessing.
const MONEY_TOKENS = /\d[\d,]*(?:\.\d+)?/g;
const HINDI_NUMBER_WORDS: Record<string, number> = {
  zero: 0, shunya: 0,
  ek: 1, aik: 1, one: 1,
  do: 2, two: 2,
  teen: 3, tin: 3, three: 3,
  char: 4, chaar: 4, four: 4,
  paanch: 5, panch: 5, five: 5,
  chhe: 6, chhah: 6, six: 6,
  saat: 7, sat: 7, seven: 7,
  aath: 8, eight: 8,
  nau: 9, nine: 9,
  das: 10, dus: 10, ten: 10,
  gyarah: 11, gyaarah: 11,
  barah: 12, baarah: 12,
  terah: 13,
  chaudah: 14,
  pandrah: 15,
  solah: 16,
  satrah: 17,
  atharah: 18,
  unnis: 19, unnees: 19,
  bees: 20, bis: 20,
  ikkis: 21, ikkees: 21,
  bais: 22, baais: 22,
  teis: 23,
  chaubis: 24,
  pachis: 25, pachees: 25,
  chhabis: 26,
  sattais: 27,
  athais: 28,
  untis: 29,
  tees: 30,
  ikattis: 31,
  battis: 32,
  taintis: 33,
  chauntis: 34,
  paintis: 35,
  chhattis: 36,
  saintis: 37,
  adhtis: 38,
  untalis: 39,
  chalis: 40,
  iktalis: 41,
  bayalis: 42,
  tetalis: 43,
  chawalis: 44,
  paintalis: 45,
  chhiyalis: 46,
  saintalis: 47,
  adtalis: 48,
  unchaas: 49,
  pachaas: 50, pachas: 50,
  ikyavan: 51,
  bavan: 52,
  tirpan: 53,
  chauvan: 54,
  pachpan: 55,
  chhappan: 56,
  sattavan: 57,
  athavan: 58,
  unsath: 59,
  saath: 60,
  iksath: 61,
  basath: 62,
  tirsath: 63,
  chaunsath: 64,
  painsath: 65,
  chhiyasath: 66,
  sadsath: 67,
  adsath: 68,
  unhattar: 69,
  sattar: 70,
  ikhattar: 71,
  bahattar: 72,
  tihattar: 73,
  chauhattar: 74,
  pachhattar: 75,
  chhihattar: 76,
  satahattar: 77,
  athhattar: 78,
  unasi: 79,
  assi: 80,
  ikyasi: 81,
  bayasi: 82,
  tirasi: 83,
  chaurasi: 84,
  pachasi: 85,
  chhiyasi: 86,
  satasi: 87,
  athasi: 88,
  navasi: 89,
  nabbe: 90,
  ikyanve: 91,
  baanve: 92,
  tiranve: 93,
  chauranve: 94,
  pachanve: 95,
  chhiyanve: 96,
  sattanve: 97,
  athanve: 98,
  ninyanve: 99,
};
const NUMBER_SCALE_WORDS: Record<string, number> = {
  sau: 100,
  hazaar: 1_000,
  hazar: 1_000,
  thousand: 1_000,
  lakh: 100_000,
  lac: 100_000,
};
const NUMBER_WORD_PATTERN = [...Object.keys(HINDI_NUMBER_WORDS), ...Object.keys(NUMBER_SCALE_WORDS)]
  .sort((left, right) => right.length - left.length)
  .join('|');
const SPELLED_RUPEE_AMOUNT = new RegExp(
  `\\b((?:${NUMBER_WORD_PATTERN})(?:\\s+(?:${NUMBER_WORD_PATTERN}))*)\\s+(?:rupaye|rupay|rupya|rupees?|rs)\\b`,
  'gi',
);
const SPOKEN_COUNT = new RegExp(
  `\\b((?:${NUMBER_WORD_PATTERN})(?:\\s+(?:${NUMBER_WORD_PATTERN}))*)\\s+(?:packs?|pieces?|bottles?|units?|items?)\\b`,
  'gi',
);

function parseSpokenNumberWords(phrase: string): number | null {
  const words = phrase.toLowerCase().trim().split(/\s+/);
  let total = 0;
  let current = 0;
  let pendingNumber: number | null = null;

  for (const word of words) {
    if (Object.hasOwn(HINDI_NUMBER_WORDS, word)) {
      if (pendingNumber !== null) return null;
      pendingNumber = HINDI_NUMBER_WORDS[word];
      continue;
    }

    const scale = NUMBER_SCALE_WORDS[word];
    if (!scale) return null;
    const multiplier = pendingNumber ?? 1;
    pendingNumber = null;

    if (scale === 100) {
      if (current !== 0) return null;
      current = multiplier * scale;
    } else {
      total += (current + multiplier) * scale;
      current = 0;
    }
  }

  const value = total + current + (pendingNumber ?? 0);
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function normalizeSpokenRupeeAmounts(value: string): string {
  return value.replace(SPELLED_RUPEE_AMOUNT, (match, numberPhrase: string) => {
    const amount = parseSpokenNumberWords(numberPhrase);
    return amount === null ? match : match.replace(numberPhrase, String(amount));
  });
}

function normalizeSpokenCount(value: string): string {
  return value.replace(SPOKEN_COUNT, (match, numberPhrase: string) => {
    const amount = parseSpokenNumberWords(numberPhrase);
    return amount === null ? match : match.replace(numberPhrase, String(amount));
  });
}

function normalizeDigits(value: string): string {
  return value.replace(/[०-९]/g, (digit) => String(digit.charCodeAt(0) - 0x0966));
}

function cleanEntityQuery(value: string): string {
  return value
    .replace(/[₹,?!।.؛،]/g, ' ')
    .replace(/\b(?:udhaar|credit|borrowed|lend|jamma|jama|repay(?:ment)?|paid|received|vasool(?:i)?|balance|baki|baaki|due|owe|owes|outstanding|khatam|stockout|sold|out|of|stock|inventory|available|remaining|left|bache|packs?|pieces?|bottles?|units?|physical|count|counted|ginti|quantity|new|add|create|register|customer|grahak|naya|nayi|jodo|banao|bana|do|how|many|much|is|are|the|what|show|check|please|tell|me|does|can|you|named|called|name|kitne|kitna|hai|hain|ka|ki|ke|ko|ne|batao|bata|set|put|to|by|voice)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function amountToPaise(rawAmount: string): number | null {
  const [groupedRupees, fraction = ''] = rawAmount.split('.');
  if (fraction.length > 2) return null;
  const validGrouping =
    /^\d+$/.test(groupedRupees) ||
    /^\d{1,2}(?:,\d{2})*,\d{3}$/.test(groupedRupees) ||
    /^\d{1,3}(?:,\d{3})+$/.test(groupedRupees);
  if (!validGrouping) return null;
  const rupees = groupedRupees.replace(/,/g, '');
  const amountPaise = Number(rupees) * 100 + Number((fraction + '00').slice(0, 2));
  return Number.isSafeInteger(amountPaise) && amountPaise > 0 ? amountPaise : null;
}

function cleanCustomerQuery(value: string): string {
  return cleanEntityQuery(value)
    .replace(/\b(?:rupees?|rupaye|rupay|rupya|rs\.?|ho|gaya|gayi|likh|kar|lo|de|dena|for|ka|ki|ke|ko|ne|of)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function clarification(message: string): ParsedMerchantCommand {
  return { status: 'clarification', message };
}

export function parseMerchantCommand(utterance: string): ParsedMerchantCommand {
  const text = normalizeSpokenRupeeAmounts(normalizeDigits(utterance)).trim();
  if (!text) return clarification('Type a command first.');

  if (PAYMENT_SUMMARY_TERMS.test(text)) return { status: 'ready', intent: 'payment_summary' };
  if (TIMELINE_SUMMARY_TERMS.test(text)) return { status: 'ready', intent: 'timeline_summary' };

  const wantsCredit = CREDIT_TERMS.test(text);
  const wantsRepayment = REPAYMENT_TERMS.test(text);
  const wantsBalance = BALANCE_TERMS.test(text);
  const wantsStockout = STOCKOUT_TERMS.test(text);
  const wantsCustomerCreate = CUSTOMER_CREATE_TERMS.test(text);
  const wantsStockCount = STOCK_COUNT_TERMS.test(text);
  const wantsStockCheck = !wantsStockCount && !wantsStockout && STOCK_CHECK_TERMS.test(text);

  const actionCount = [wantsCredit, wantsRepayment, wantsBalance, wantsStockout, wantsCustomerCreate, wantsStockCheck, wantsStockCount].filter(Boolean).length;
  if (actionCount > 1) {
    return clarification('I found more than one action. Please enter one command at a time.');
  }

  if (wantsCustomerCreate) {
    const customerName = cleanCustomerQuery(text);
    if (!customerName) return clarification('What exact customer name should I add? Try “add new customer Raju Sharma.”');
    if (customerName.length > 100) return clarification('That customer name is too long. Please use a shorter name.');
    return { status: 'ready', intent: 'customer_create', customerName };
  }

  if (wantsStockout) {
    const productQuery = cleanCustomerQuery(text);
    return productQuery
      ? { status: 'ready', intent: 'stockout', productQuery }
      : clarification('Which product is out of stock? Try “Maggi khatam ho gaya.”');
  }

  if (wantsStockCount) {
    const countText = normalizeSpokenCount(text);
    const numberMatches = [...countText.matchAll(MONEY_TOKENS)];
    if (numberMatches.length !== 1) {
      return clarification('Say one whole-number count, for example “set Maggi stock count to 10 packs.”');
    }
    const rawCount = numberMatches[0][0];
    if (rawCount.includes('.')) return clarification('Stock count must be a whole number.');
    const grouped = rawCount.replace(/,/g, '');
    const countedQuantity = Number(grouped);
    if (!Number.isSafeInteger(countedQuantity) || countedQuantity < 0) {
      return clarification('Stock count must be a non-negative whole number.');
    }
    const productQuery = cleanEntityQuery(countText.replace(rawCount, ' '));
    if (!productQuery) return clarification('Which product should I count? Try “set Maggi stock count to 10 packs.”');
    return { status: 'ready', intent: 'stock_count', productQuery, countedQuantity };
  }

  if (wantsStockCheck) {
    const productQuery = cleanEntityQuery(text);
    return productQuery
      ? { status: 'ready', intent: 'stock_check', productQuery }
      : clarification('Which product should I check? Try “how many Maggi packs are left?”');
  }

  if (wantsBalance && !wantsCredit && !wantsRepayment) {
    const customerQuery = cleanCustomerQuery(text);
    return customerQuery
      ? { status: 'ready', intent: 'balance', customerQuery }
      : clarification('Whose balance should I check? Try “Raju bhai ka balance batao.”');
  }

  if (!wantsCredit && !wantsRepayment) {
    return {
      status: 'unsupported',
      message: 'Try a customer balance, credit, repayment, add-customer, stock check/count, payment summary, or activity summary command.',
    };
  }

  const numberMatches = [...text.matchAll(MONEY_TOKENS)];
  if (numberMatches.length === 0) {
    return clarification('I could not find an amount. For Hindi speech, say the number with “rupaye”, for example “das rupaye”.');
  }
  if (numberMatches.length > 1) {
    return clarification('I found more than one amount. Please say one amount, for example “Raju bhai ka das rupaye udhaar likh do.”');
  }

  const amountMatch = numberMatches[0];
  const rawAmount = amountMatch[0];
  const amountPaise = amountToPaise(rawAmount);
  if (amountPaise === null) {
    return clarification('Enter a positive amount with valid comma grouping and no more than two decimal places.');
  }

  const beforeAmount = text.slice(0, amountMatch.index);
  const afterAmount = text.slice((amountMatch.index ?? 0) + rawAmount.length);
  const customerQuery = cleanCustomerQuery(`${beforeAmount} ${afterAmount}`);
  if (!customerQuery) {
    return clarification('Which customer is this for? Include their name, for example “Raju bhai ka ₹50 udhaar.”');
  }
  if (customerQuery.length > 100) {
    return clarification('That customer name is too long. Please use a shorter exact name or alias.');
  }

  return {
    status: 'ready',
    intent: wantsCredit ? 'credit' : 'repayment',
    customerQuery,
    amountPaise,
  };
}
