import type { CarClass, ServiceId } from './data'
import type { Booking } from './store'
import { TG } from './tg'

// Живой режим: сборка на сервере Глянца (VITE_API=1) и запуск из Telegram — тогда записи,
// слоты и оплата идут через сервер. Иначе (GitHub Pages, браузер) — демо в localStorage.
export const LIVE = import.meta.env.VITE_API === '1' && !!TG

// Студия в Москве, расписание — по московским часам, а телефон клиента может жить в любом
// поясе. В живом режиме мини-апп считает в «московских настенных часах»: даты с сервера и
// текущее время сдвигаются так, чтобы getHours() возвращал московский час.
export const SHIFT = LIVE ? (180 + new Date().getTimezoneOffset()) * 60000 : 0
export const clock = () => Date.now() + SHIFT
const wall = <T extends Booking>(b: T): T => ({
  ...b,
  start: new Date(Date.parse(b.start) + SHIFT).toISOString(),
  ready: new Date(Date.parse(b.ready) + SHIFT).toISOString(),
})

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-Init-Data': TG?.initData ?? '' },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, typeof body.detail === 'string' ? body.detail : 'Не получилось, попробуйте ещё раз')
  }
  return response.json()
}

export type Slot = { time: string; free: boolean }
export type NewBooking = {
  services: ServiceId[]
  cls: CarClass
  day: string
  time: string
  car: string
  plate: string
  name: string
  phone: string
}

export const api = {
  config: () => call<{ prepay_percent: number }>('api/config'),
  bookings: () => call<Booking[]>('api/bookings').then(list => list.map(wall)),
  slots: (day: string, cls: CarClass, services: ServiceId[]) =>
    call<{ slots: Slot[] }>(`api/slots?day=${day}&cls=${cls}&services=${services.join(',')}`).then(r => r.slots),
  book: (body: NewBooking) =>
    call<Booking & { invoice: string | null }>('api/bookings', { method: 'POST', body: JSON.stringify(body) }).then(wall),
  move: (id: string, day: string, time: string) =>
    call<Booking>(`api/bookings/${id}`, { method: 'PATCH', body: JSON.stringify({ day, time }) }).then(wall),
  cancel: (id: string) => call<Booking>(`api/bookings/${id}`, { method: 'DELETE' }).then(wall),
}

export const isoDay = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

export function pay(url: string): Promise<boolean> {
  if (!TG?.openInvoice) return Promise.resolve(false)
  return new Promise(resolve => TG!.openInvoice!(url, status => resolve(status === 'paid')))
}
