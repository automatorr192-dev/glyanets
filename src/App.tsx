import { CalendarCheck, CaretLeft, Sparkle, Storefront } from '@phosphor-icons/react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Toast } from './components/ui'
import { useBackButton } from './hooks/useBackButton'
import { useHaptic } from './hooks/useHaptic'
import { quote, readyAt, type CarClass, type ServiceId } from './lib/data'
import { load, save, type Booking } from './lib/store'
import { confirm, userName, TG } from './lib/tg'
import { Book } from './views/Book'
import { Bookings } from './views/Bookings'
import { Confirm } from './views/Confirm'
import { Detail } from './views/Detail'
import { Done } from './views/Done'
import { Home } from './views/Home'
import { Studio } from './views/Studio'
import { startOf, Time } from './views/Time'

export type Draft = {
  services: ServiceId[]
  cls: CarClass
  day: number
  time: string | null
  car: string
  plate: string
  name: string
  phone: string
}

type Tab = 'home' | 'bookings' | 'studio'
type Route =
  | { name: Tab }
  | { name: 'book' }
  | { name: 'time' }
  | { name: 'confirm' }
  | { name: 'done'; id: string }
  | { name: 'detail'; id: string }
type Entry = Route & { key: number }

const TABS: { id: Tab; name: string; icon: ReactNode }[] = [
  { id: 'home', name: 'Услуги', icon: <Sparkle size={22} weight="fill" /> },
  { id: 'bookings', name: 'Записи', icon: <CalendarCheck size={22} weight="fill" /> },
  { id: 'studio', name: 'Студия', icon: <Storefront size={22} weight="fill" /> },
]

let seq = 0
const entry = (r: Route): Entry => ({ ...r, key: ++seq })
const PUSH_MS = 500

function useNow(ms: number) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

export default function App() {
  const haptic = useHaptic()
  const now = useNow(20_000)
  const [bookings, setBookings] = useState<Booking[]>(load)
  const [stack, setStack] = useState<Entry[]>([entry({ name: 'home' })])
  const [entering, setEntering] = useState<number | null>(null)
  const [ghost, setGhost] = useState<Entry | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<number>(0)
  const last = useRef<Booking[] | null>(null)
  const [draft, setDraft] = useState<Draft>({
    services: [],
    cls: 'sedan',
    day: 0,
    time: null,
    car: '',
    plate: '',
    name: userName() === 'Гость' ? '' : userName(),
    phone: '',
  })

  useEffect(() => {
    if (last.current) save(bookings)
    last.current = bookings
  }, [bookings])

  const set = useCallback((patch: Partial<Draft>) => setDraft(d => ({ ...d, ...patch })), [])

  const flash = (text: string) => {
    setToast(text)
    clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 2200)
  }

  const push = (r: Route) => {
    const e = entry(r)
    setStack(s => [...s, e])
    setEntering(e.key)
    requestAnimationFrame(() => requestAnimationFrame(() => setEntering(null)))
  }

  const pop = () => {
    if (stack.length < 2) return
    const top = stack[stack.length - 1]
    setGhost(top)
    setStack(s => s.slice(0, -1))
    window.setTimeout(() => setGhost(g => (g?.key === top.key ? null : g)), PUSH_MS)
  }

  const reset = (r: Route) => {
    setGhost(null)
    setStack([entry(r)])
  }

  useBackButton(pop, stack.length > 1)

  const startBooking = (ids: ServiceId[] = []) => {
    set({ services: ids, time: null })
    push({ name: 'book' })
  }

  const submit = () => {
    const q = quote(draft.services, draft.cls)
    const start = startOf(draft)
    const b: Booking = {
      id: `b${Date.now()}`,
      services: draft.services,
      cls: draft.cls,
      car: draft.car.trim(),
      plate: draft.plate.trim(),
      start: start.toISOString(),
      ready: readyAt(start, q.hours).toISOString(),
      total: q.total,
      phone: draft.phone,
    }
    setBookings(list => [...list, b])
    haptic.success()
    setDraft(d => ({ ...d, services: [], time: null, day: 0 }))
    setGhost(null)
    setStack([entry({ name: 'home' }), entry({ name: 'done', id: b.id })])
  }

  const cancel = async (id: string) => {
    if (!(await confirm('Отменить запись? Время освободится для других.'))) return
    setBookings(list => list.map(b => (b.id === id ? { ...b, cancelled: true } : b)))
    haptic.error()
    flash('Запись отменена')
    pop()
  }

  const find = (id: string) => bookings.find(b => b.id === id)

  const render = (r: Entry, isTop: boolean) => {
    switch (r.name) {
      case 'home':
        return <Home bookings={bookings} now={now} onBook={startBooking} onOpen={id => push({ name: 'detail', id })} />
      case 'bookings':
        return <Bookings bookings={bookings} now={now} onOpen={id => push({ name: 'detail', id })} onBook={() => startBooking()} />
      case 'studio':
        return <Studio />
      case 'book':
        return <Book draft={draft} set={set} isTop={isTop} onNext={() => push({ name: 'time' })} />
      case 'time':
        return <Time draft={draft} set={set} bookings={bookings} now={now} isTop={isTop} onNext={() => push({ name: 'confirm' })} />
      case 'confirm':
        return <Confirm draft={draft} set={set} now={now} isTop={isTop} onSubmit={submit} />
      case 'done': {
        const b = find(r.id)
        return b ? <Done booking={b} now={now} onBookings={() => reset({ name: 'bookings' })} onHome={() => reset({ name: 'home' })} /> : null
      }
      case 'detail': {
        const b = find(r.id)
        return b ? <Detail booking={b} now={now} onCancel={() => cancel(b.id)} /> : null
      }
    }
  }

  const root = stack[0].name as Tab
  const tabsVisible = stack.length === 1 && !ghost

  return (
    <div className="app">
      {(ghost ? [...stack, ghost] : stack).map((r, i) => {
        const leaving = ghost?.key === r.key
        const isTop = !leaving && i === stack.length - 1
        const cls = leaving ? ' leave' : isTop ? (r.key === entering ? ' enter' : '') : ' under'
        const hidden = !leaving && i < stack.length - 2
        const tabRoot = i === 0 && !leaving && ['home', 'bookings', 'studio'].includes(r.name)
        return (
          <main
            key={r.key}
            className={`screen${cls}${tabRoot ? '' : ' no-tabs'}`}
            style={hidden ? { visibility: 'hidden' } : undefined}
            aria-hidden={!isTop}
            inert={!isTop}
          >
            {render(r, isTop)}
          </main>
        )
      })}

      <nav className={`tabbar${tabsVisible ? '' : ' hidden'}`} aria-label="Разделы">
        {TABS.map(t => (
          <button
            key={t.id}
            type="button"
            aria-current={root === t.id ? 'page' : undefined}
            onClick={() => {
              if (root !== t.id) {
                haptic.select()
                reset({ name: t.id })
              }
            }}
          >
            {t.icon}
            {t.name}
          </button>
        ))}
      </nav>

      {!TG && stack.length > 1 && (
        <button className="web-back" type="button" onClick={pop} aria-label="Назад">
          <CaretLeft size={22} weight="bold" />
          Назад
        </button>
      )}
      <Toast text={toast} />
    </div>
  )
}
