type Haptic = {
  impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
  notificationOccurred(type: 'error' | 'success' | 'warning'): void
  selectionChanged(): void
}

type BottomButton = {
  setParams(p: { text?: string; color?: string; text_color?: string; is_active?: boolean; is_visible?: boolean }): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
  show(): void
  hide(): void
}

type Inset = { top: number; bottom: number; left: number; right: number }

export type WebApp = {
  platform: string
  version: string
  colorScheme: 'light' | 'dark'
  initDataUnsafe: { user?: { first_name?: string; last_name?: string; photo_url?: string } }
  safeAreaInset?: Inset
  contentSafeAreaInset?: Inset
  MainButton: BottomButton
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void }
  HapticFeedback: Haptic
  ready(): void
  expand(): void
  setHeaderColor(color: string): void
  setBackgroundColor(color: string): void
  setBottomBarColor?(color: string): void
  onEvent(event: string, cb: () => void): void
  offEvent(event: string, cb: () => void): void
  showConfirm?(message: string, cb: (ok: boolean) => void): void
  requestContact?(cb: (ok: boolean, res?: { responseUnsafe?: { contact?: { phone_number?: string } } }) => void): void
  openLink(url: string): void
  isVersionAtLeast(v: string): boolean
  disableVerticalSwipes?(): void
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp }
  }
}

const WA = window.Telegram?.WebApp
export const TG: WebApp | null = WA && WA.platform !== 'unknown' ? WA : null

if (!TG) document.body.classList.add('no-tg')

export function userName(): string {
  return TG?.initDataUnsafe.user?.first_name || 'Гость'
}

export function scheme(): 'light' | 'dark' {
  if (TG) return TG.colorScheme
  return matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

const BG = { dark: '#08080a', light: '#f2f2f7' }

export function applyTheme() {
  const s = scheme()
  document.documentElement.dataset.theme = s
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BG[s])
  try {
    TG?.setHeaderColor(BG[s])
    TG?.setBackgroundColor(BG[s])
    TG?.setBottomBarColor?.(BG[s])
  } catch {
    /* старые клиенты Telegram не знают этих методов */
  }
}

export function applyInsets() {
  const root = document.documentElement.style
  const a = TG?.safeAreaInset, c = TG?.contentSafeAreaInset
  root.setProperty('--tg-top', `${(a?.top ?? 0) + (c?.top ?? 0)}px`)
  root.setProperty('--tg-bottom', `${(a?.bottom ?? 0) + (c?.bottom ?? 0)}px`)
}

export function confirm(message: string): Promise<boolean> {
  if (TG?.showConfirm && TG.isVersionAtLeast('6.2')) return new Promise(r => TG!.showConfirm!(message, r))
  return Promise.resolve(window.confirm(message))
}

export function requestPhone(): Promise<string | null> {
  if (!TG?.requestContact || !TG.isVersionAtLeast('6.9')) return Promise.resolve(null)
  return new Promise(r =>
    TG!.requestContact!((ok, res) => r(ok ? res?.responseUnsafe?.contact?.phone_number ?? null : null)),
  )
}

export function openLink(url: string) {
  if (TG) TG.openLink(url)
  else window.open(url, '_blank', 'noopener')
}
