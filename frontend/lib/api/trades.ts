import { apiFetch } from './server'
import type { TradeRef, TradeUpdate } from './types'

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

/** Update a trade's Brenk-internal fields (default markup %, etc.).
 *  Omit a field to leave it alone; set to null to clear. */
export function updateTrade(id: number, body: TradeUpdate): Promise<TradeRef> {
  return apiFetch<TradeRef>(`/api/v1/trades/${id}`, {
    method: 'PATCH',
    body,
  })
}
