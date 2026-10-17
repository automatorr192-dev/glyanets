import { useEffect, useMemo, useState } from 'react'
import { BottomAction, Group, NavBar, Segmented, Steps } from '../components/ui'
import { api, isoDay, LIVE, type Slot } from '../lib/api'
import { quote, readyAt, slotsFor, type CarClass, type ServiceId } from '../lib/data'
import { hm, relDay, sameDay, weekday } from '../lib/format'
import { status, type Booking } from '../lib/store'
import { useHaptic } from '../hooks/useHaptic'
import type { Draft } from '../App'

const MONTH = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

const PARTS = [
  { id: 'morning', name: 'Утро', to: 12 },
  { id: 'day', name: 'День', to: 17 },
  { id: 'evening', name: 'Вечер', to: 24 },
] as const
type Part = (typeof PARTS)[number]['id']
const partOf = (time: string) => PARTS.find(p => Number(time.slice(0, 2)) < p.to)!.id

export function dayAt(offset: number, now = Date.now()) {
  const d = new Date(now)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + offset)
  return d
}

export function startOf(draft: Draft, now = Date.now()) {
  const d = dayAt(draft.day, now)
  const [h, m] = (draft.time ?? '09:00').split(':').map(Number)
  d.setHours(h, m, 0, 0)
  return d
}

// В живом режиме занятость знает только сервер: боксы, чужие записи, неоплаченные брони.
function useSlots(day: Date, hours: number, taken: string[], now: number, services: ServiceId[], cls: CarClass) {
  const local = useMemo(() => slotsFor(day, hours, taken, new Date(now)), [day.getTime(), hours, taken.join(), now])
  const [remote, setRemote] = useState<Slot[] | null>(null)
  useEffect(() => {
    if (!LIVE) return
    let alive = true
    setRemote(null)
    api.slots(isoDay(day), cls, services).then(s => alive && setRemote(s)).catch(() => alive && setRemote([]))
    return () => {
      alive = false
    }
  }, [day.getTime(), cls, services.join()])
  return LIVE ? (remote ?? []) : local
}

type Props = { draft: Draft; set: (patch: Partial<Draft>) => void; bookings: Booking[]; now: number; onNext: () => void; isTop: boolean }

export function Time({ draft, set, bookings, now, onNext, isTop }: Props) {
  const haptic = useHaptic()
  const q = quote(draft.services, draft.cls)
  const hours = q.hours
  const day = dayAt(draft.day, now)
  const takenOn = (d: Date) =>
    bookings.filter(b => status(b, now) !== 'cancelled' && sameDay(new Date(b.start), d)).map(b => hm(new Date(b.start)))
  const taken = takenOn(day)
  const slots = useSlots(day, hours, taken, now, draft.services, draft.cls)
  const days = useMemo(() => Array.from({ length: 14 }, (_, i) => dayAt(i, now)), [now])
  const today = days[0]
  const todaySlots = useSlots(today, hours, takenOn(today), now, draft.services, draft.cls)
  const todayFull = (!LIVE || todaySlots.length > 0) && !todaySlots.some(s => s.free)
  const [part, setPart] = useState<Part | null>(null)

  useEffect(() => {
    if (draft.day === 0 && todayFull) set({ day: 1, time: null })
  }, [draft.day, todayFull])

  const parts = PARTS.map(p => ({ ...p, slots: slots.filter(s => partOf(s.time) === p.id) })).filter(p => p.slots.length)
  const firstFree = parts.find(p => p.slots.some(s => s.free)) ?? parts[0]
  const shown = parts.find(p => p.id === (part ?? (draft.time ? partOf(draft.time) : firstFree?.id))) ?? firstFree
  const ready = draft.time ? readyAt(startOf(draft, now), hours) : null

  return (
    <>
      <NavBar title="Запись" />
      <Steps at={1} />

      <h2 className="group-head inner rise" style={{ padding: '22px var(--gutter) 0' }}>
        {MONTH[day.getMonth()]}
      </h2>
      <div className="days rise" role="group" aria-label="День визита" style={{ ['--i' as string]: 1 }}>
        {days.map((d, i) => (
          <button
            key={i}
            type="button"
            className={`day${d.getDay() === 0 || d.getDay() === 6 ? ' weekend' : ''}`}
            aria-pressed={i === draft.day}
            aria-label={i === 0 && todayFull ? 'Сегодня, мест нет' : relDay(d, new Date(now))}
            disabled={i === 0 && todayFull}
            onClick={() => {
              haptic.select()
              setPart(null)
              set({ day: i, time: null })
            }}
          >
            <small>{i === 0 ? 'сегодня' : weekday(d)}</small>
            <b>{d.getDate()}</b>
          </button>
        ))}
      </div>

      <Group
        head="Время приёма"
        i={2}
        foot={
          ready
            ? `Заберёте ${relDay(ready, new Date(now))} после ${hm(ready)}.`
            : todayFull && draft.day === 1
              ? 'На сегодня свободного времени уже нет, ближайшее завтра.'
              : hours >= 6
                ? 'Долгие работы начинаем утром, машина остаётся у нас.'
                : 'Время с пометкой «занято» уже забрали.'
        }
      >
        {!shown && <p className="slots-wait">Смотрим свободное время…</p>}
        {shown && parts.length > 1 && (
          <Segmented
            label="Часть дня"
            items={parts.map(p => ({ id: p.id, name: <>{p.name} <small>{p.slots.filter(s => s.free).length}</small></> }))}
            value={shown.id}
            onChange={setPart}
          />
        )}
        <div className="slots" role="group" aria-label="Время приёма">
          {shown?.slots.map(s => (
            <button
              key={s.time}
              type="button"
              className="slot"
              disabled={!s.free}
              aria-pressed={s.time === draft.time}
              aria-label={s.free ? s.time : `${s.time}, занято`}
              onClick={() => {
                haptic.select()
                set({ time: s.time })
              }}
            >
              {s.time}
              {!s.free && <small>занято</small>}
            </button>
          ))}
        </div>
      </Group>

      <BottomAction
        visible={isTop}
        active={!!draft.time}
        text={draft.time ? (draft.moving ? 'Перенести сюда' : 'Продолжить') : 'Выберите время'}
        total={draft.moving ? undefined : q.total}
        onClick={onNext}
      />
    </>
  )
}
