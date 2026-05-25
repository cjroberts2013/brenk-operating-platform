'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import { updateTrade } from '@/lib/api/trades'

export type TradeMarkupResult = { error: string | null }

/** Set a trade's default markup %. Empty string clears the default. */
export async function setTradeMarkupAction(
  tradeId: number,
  rawPercent: string,
): Promise<TradeMarkupResult> {
  const trimmed = rawPercent.trim()
  const value: string | null = trimmed.length ? trimmed : null
  if (value !== null) {
    const n = Number(value)
    if (!Number.isFinite(n) || n < 0 || n > 1000) {
      return { error: 'Default must be a number between 0 and 1000.' }
    }
  }
  try {
    await updateTrade(tradeId, { default_markup_percent: value })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath('/settings')
  // Also revalidate any open WO detail so a fresh "suggested" line
  // shows up on the next visit.
  revalidatePath('/work-orders', 'layout')
  return { error: null }
}
