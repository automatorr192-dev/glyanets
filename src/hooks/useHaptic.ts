import { TG } from '../lib/tg'

function safe(fn: () => void) {
  try {
    fn()
  } catch {
    /* вне Telegram и в старых клиентах хаптика нет: тихо пропускаем */
  }
}

export function useHaptic() {
  return {
    tap: () => safe(() => TG?.HapticFeedback.impactOccurred('light')),
    select: () => safe(() => TG?.HapticFeedback.selectionChanged()),
    success: () => safe(() => TG?.HapticFeedback.notificationOccurred('success')),
    error: () => safe(() => TG?.HapticFeedback.notificationOccurred('error')),
  }
}
