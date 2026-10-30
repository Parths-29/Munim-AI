export type MerchantCommandIntent = 'credit' | 'repayment' | 'balance' | 'stockout';

export type ParsedMerchantCommand =
  | {
      status: 'ready';
      intent: 'credit' | 'repayment';
      customerQuery: string;
      amountPaise: number;
    }
  | { status: 'ready'; intent: 'balance'; customerQuery: string }
  | { status: 'ready'; intent: 'stockout'; productQuery: string }
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
const BALANCE_TERMS = /\b(?:balance|baki|baaki|due)\b|kitna\s+udhaar/i;
const STOCKOUT_TERMS = /\b(?:khatam|stockout|sold\s+out|out\s+of\s+stock)\b/i;
// Keep common Indian and western thousands separators inside one amount token.
// Validation below rejects malformed grouping rather than guessing.
const MONEY_TOKENS = /\d[\d,]*(?:\.\d+)?/g;

function normalizeDigits(value: string): string {
  return value.replace(/[०-९]/g, (digit) => String(digit.charCodeAt(0) - 0x0966));
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
  return value
    .replace(/[₹,?!।]/g, ' ')
    .replace(/\b(?:udhaar|credit|borrowed|lend|jamma|jama|repay(?:ment)?|paid|received|vasool(?:i)?|balance|baki|baaki|due|khatam|stockout|sold|out|of|stock|ho|gaya|gayi|rupees?|rupaye|rupya|rs\.?|likh|batao|bata|kar|lo|do|de|dena|please|for|customer)\b/gi, ' ')
    .replace(/\b(?:ka|ki|ke|ko|ne|of)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function clarification(message: string): ParsedMerchantCommand {
  return { status: 'clarification', message };
}

export function parseMerchantCommand(utterance: string): ParsedMerchantCommand {
  const text = normalizeDigits(utterance).trim();
  if (!text) return clarification('Type a command first.');

  const wantsCredit = CREDIT_TERMS.test(text);
  const wantsRepayment = REPAYMENT_TERMS.test(text);
  const wantsBalance = BALANCE_TERMS.test(text);
  const wantsStockout = STOCKOUT_TERMS.test(text);

  const actionCount = [wantsCredit, wantsRepayment, wantsBalance, wantsStockout].filter(Boolean).length;
  if (actionCount > 1) {
    return clarification('I found more than one action. Please enter one command at a time.');
  }

  if (wantsStockout) {
    const productQuery = cleanCustomerQuery(text);
    return productQuery
      ? { status: 'ready', intent: 'stockout', productQuery }
      : clarification('Which product is out of stock? Try “Maggi khatam ho gaya.”');
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
      message: 'I can handle udhaar, jama, and balance commands here. Try “Raju bhai ka ₹50 udhaar likh do.”',
    };
  }

  const numberMatches = [...text.matchAll(MONEY_TOKENS)];
  if (numberMatches.length !== 1) {
    return clarification('I need exactly one amount. Try “Raju bhai ka ₹50 udhaar likh do.”');
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
