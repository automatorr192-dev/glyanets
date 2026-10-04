export type CarClass = 'sedan' | 'suv' | 'large'
export type ServiceId = 'wash' | 'polish' | 'ceramic' | 'interior' | 'ppf'

export type Service = {
  id: ServiceId
  name: string
  short: string
  hours: number
  price: Record<CarClass, number>
  includes: string[]
}

export const CLASSES: { id: CarClass; name: string }[] = [
  { id: 'sedan', name: 'Седан' },
  { id: 'suv', name: 'Кроссовер' },
  { id: 'large', name: 'Внедорожник' },
]

export const SERVICES: Service[] = [
  {
    id: 'wash',
    name: 'Детейлинг-мойка',
    short: 'Двухфазная мойка, сушка, чернение шин',
    hours: 1.5,
    price: { sedan: 2500, suv: 2900, large: 3400 },
    includes: ['Бесконтактная и ручная фаза', 'Чистка дисков', 'Сушка воздухом', 'Чернение шин'],
  },
  {
    id: 'polish',
    name: 'Полировка кузова',
    short: 'Убираем голограммы и мелкие царапины',
    hours: 8,
    price: { sedan: 18000, suv: 22000, large: 26000 },
    includes: ['Замер толщины ЛКП', 'Абразивная полировка в два этапа', 'Обезжиривание'],
  },
  {
    id: 'ceramic',
    name: 'Керамика',
    short: 'Два слоя, гарантия 2 года',
    hours: 8,
    price: { sedan: 28000, suv: 34000, large: 40000 },
    includes: ['Подготовка поверхности', 'Два слоя состава', 'ИК-сушка', 'Контроль в боксе с освещением'],
  },
  {
    id: 'interior',
    name: 'Химчистка салона',
    short: 'Сиденья, потолок, ковры, пластик',
    hours: 6,
    price: { sedan: 12000, suv: 14000, large: 16000 },
    includes: ['Экстрактор на ткань', 'Кожа: очистка и пропитка', 'Озонирование'],
  },
  {
    id: 'ppf',
    name: 'Бронеплёнка',
    short: 'Капот, бампер, фары, зеркала',
    hours: 16,
    price: { sedan: 45000, suv: 52000, large: 60000 },
    includes: ['Полиуретан 190 мкм', 'Заворот кромок', 'Лекала под модель'],
  },
]

export const byId = (id: ServiceId) => SERVICES.find(s => s.id === id)!

export const BUNDLE_OFF = 0.1

export function quote(ids: ServiceId[], cls: CarClass) {
  const items = ids.map(id => ({ id, name: byId(id).name, price: byId(id).price[cls] }))
  const subtotal = items.reduce((a, b) => a + b.price, 0)
  const bundle = ids.includes('polish') && ids.includes('ceramic')
  const discount = bundle ? Math.round((byId('polish').price[cls] + byId('ceramic').price[cls]) * BUNDLE_OFF / 100) * 100 : 0
  const hours = ids.reduce((a, id) => a + byId(id).hours, 0)
  return { items, subtotal, discount, total: subtotal - discount, hours, bundle }
}

export const OPEN_HOUR = 9
export const CLOSE_HOUR = 21

export function slotsFor(day: Date, hours: number, taken: string[], now = new Date()): { time: string; free: boolean }[] {
  const out: { time: string; free: boolean }[] = []
  const last = hours >= 6 ? 11 : CLOSE_HOUR - Math.ceil(hours)
  for (let h = OPEN_HOUR; h <= last; h += hours >= 6 ? 1 : 0.5) {
    const at = new Date(day)
    at.setHours(Math.floor(h), h % 1 ? 30 : 0, 0, 0)
    const time = `${String(Math.floor(h)).padStart(2, '0')}:${h % 1 ? '30' : '00'}`
    const busy = taken.includes(time) || hashBusy(day, time)
    out.push({ time, free: at.getTime() > now.getTime() + 60 * 60 * 1000 && !busy })
  }
  return out
}

function hashBusy(day: Date, time: string) {
  const key = `${day.getMonth()}-${day.getDate()}-${time}`
  let h = 0
  for (const c of key) h = (h * 31 + c.charCodeAt(0)) | 0
  return Math.abs(h) % 4 === 0
}

export function readyAt(start: Date, hours: number): Date {
  const end = new Date(start)
  let left = hours
  while (left > 0) {
    const closing = new Date(end)
    closing.setHours(CLOSE_HOUR, 0, 0, 0)
    const room = Math.max(0, (closing.getTime() - end.getTime()) / 3.6e6)
    if (left <= room) {
      end.setTime(end.getTime() + left * 3.6e6)
      left = 0
    } else {
      left -= room
      end.setDate(end.getDate() + 1)
      end.setHours(OPEN_HOUR, 0, 0, 0)
    }
  }
  return end
}

export const STAGES: Record<ServiceId, string[]> = {
  wash: ['Мойка', 'Сушка'],
  polish: ['Замер ЛКП', 'Полировка', 'Финиш'],
  ceramic: ['Подготовка', 'Нанесение', 'ИК-сушка'],
  interior: ['Разбор', 'Чистка', 'Сушка'],
  ppf: ['Подготовка', 'Оклейка', 'Контроль'],
}

export const STUDIO = {
  address: 'Москва, Ходынский бульвар',
  metro: 'ЦСКА',
  hours: 'Ежедневно 9:00-21:00',
  phone: '+7 495 000-00-00',
  map: 'https://yandex.ru/maps/?text=%D0%A5%D0%BE%D0%B4%D1%8B%D0%BD%D1%81%D0%BA%D0%B8%D0%B9%20%D0%B1%D1%83%D0%BB%D1%8C%D0%B2%D0%B0%D1%80',
}
