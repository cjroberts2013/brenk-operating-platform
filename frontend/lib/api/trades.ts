import { apiFetch } from './server'
import type { TradeRef } from './types'

/** Returns all trades, ordered by name. Small list — no pagination. */
export function listTrades(): Promise<TradeRef[]> {
  return apiFetch<TradeRef[]>('/api/v1/trades/')
}

/** Create a Brenk-internal trade (sc_trade_id will be null). Uniqueness
 *  is enforced case-insensitively by the backend. */
export function createTrade(name: string): Promise<TradeRef> {
  return apiFetch<TradeRef>('/api/v1/trades/', {
    method: 'POST',
    body: { name },
  })
}
