const nf = new Intl.NumberFormat('ru-RU')

export const rub = (n: number) => `${nf.format(n)} ₽`

const DAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

export const weekday = (d: Date) => DAYS[d.getDay()]
export const dayMonth = (d: Date) => `${d.getDate()} ${MONTHS[d.getMonth()]}`
export const hm = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

export function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

export function relDay(d: Date, now = new Date()) {
  const t = new Date(now)
  if (sameDay(d, t)) return 'сегодня'
  t.setDate(t.getDate() + 1)
  if (sameDay(d, t)) return 'завтра'
  return `${dayMonth(d)}, ${weekday(d)}`
}

export function duration(hours: number) {
  if (hours <= 4) return `${String(hours).replace('.', ',')} ч`
  const days = Math.ceil(hours / 8)
  return days === 1 ? '1 день' : `${days} дня`
}

export function plural(n: number, one: string, few: string, many: string) {
  const m = n % 10, h = n % 100
  return m === 1 && h !== 11 ? one : m >= 2 && m <= 4 && (h < 12 || h > 14) ? few : many
}
