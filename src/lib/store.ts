import { readyAt, type CarClass, type ServiceId } from './data'

export type Booking = {
  id: string
  services: ServiceId[]
  cls: CarClass
  car: string
  plate: string
  start: string
  ready: string
  total: number
  phone?: string
  cancelled?: boolean
}

export type Status = 'upcoming' | 'in_work' | 'done' | 'cancelled'

const KEY = 'glyanets.bookings.v2'

export function status(b: Booking, now = Date.now()): Status {
  if (b.cancelled) return 'cancelled'
  if (now < Date.parse(b.start)) return 'upcoming'
  if (now < Date.parse(b.ready)) return 'in_work'
  return 'done'
}

export function progress(b: Booking, now = Date.now()) {
  const s = Date.parse(b.start), e = Date.parse(b.ready)
  return Math.min(1, Math.max(0, (now - s) / (e - s)))
}

function seed(): Booking[] {
  const now = new Date(), h = 3.6e6
  // Демо-машина в работе приехала к 10 утра (сегодня или вчера, если ещё рано), а срок
  // считается по часам работы студии: «готово в час ночи» на витрине выглядело бы враньём.
  const start = new Date(now)
  start.setHours(10, 0, 0, 0)
  if (now.getTime() < start.getTime() + 0.5 * h) start.setDate(start.getDate() - 1)
  const past = new Date(start.getTime() - 12 * 24 * h)
  return [
    {
      id: 'demo-active',
      services: ['polish', 'ceramic'],
      cls: 'sedan',
      car: 'Kia K5',
      plate: 'К 512 ОМ 799',
      start: start.toISOString(),
      ready: readyAt(start, 16).toISOString(),
      total: 41400,
    },
    {
      id: 'demo-past',
      services: ['wash'],
      cls: 'sedan',
      car: 'Kia K5',
      plate: 'К 512 ОМ 799',
      start: past.toISOString(),
      ready: new Date(past.getTime() + 1.5 * h).toISOString(),
      total: 2500,
    },
  ]
}

export function load(): Booking[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return JSON.parse(raw) as Booking[]
  } catch {
    /* приватный режим или битые данные: начинаем с демо */
  }
  return seed()
}

export function save(list: Booking[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    /* хранилище недоступно: записи живут до закрытия аппа */
  }
}
