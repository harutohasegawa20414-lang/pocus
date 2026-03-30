/** 無効・空・'#' を null に、プロトコルなしURLに https:// を付与して返す。
 *  javascript: / data: 等の危険なプロトコルはブロックする。 */
export function normalizeUrl(url: string | null | undefined): string | null {
  if (!url) return null
  const trimmed = url.trim()
  if (!trimmed || trimmed === '#') return null
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed
  // javascript:, data:, vbscript: 等を明示的にブロック
  if (/^[a-z]+:/i.test(trimmed)) return null
  return `https://${trimmed}`
}
