import { Check } from '@phosphor-icons/react'
import { Cell, Group, NavBar } from '../components/ui'
import { LiveActivity, stagesOf } from '../components/LiveActivity'
import { byId, STUDIO } from '../lib/data'
import { dayMonth, hm, relDay, rub, weekday } from '../lib/format'
import { progress, status, type Booking } from '../lib/store'
import { STATUS_RU } from './Bookings'

type Props = { booking: Booking; now: number; onCancel: () => void }

export function Detail({ booking, now, onCancel }: Props) {
  const s = status(booking, now)
  const start = new Date(booking.start), ready = new Date(booking.ready)
  const stages = stagesOf(booking)
  const current = s === 'in_work' ? Math.min(stages.length - 1, Math.floor(progress(booking, now) * stages.length)) : s === 'done' ? stages.length : -1

  return (
    <>
      <NavBar title={STATUS_RU[s]} />

      {s === 'in_work' ? (
        <LiveActivity booking={booking} now={now} />
      ) : (
        <Group i={0}>
          <Cell
            title={<b style={{ fontSize: 20 }}>{`${dayMonth(start)}, ${weekday(start)}`}</b>}
            sub={s === 'upcoming' ? `Приём в ${hm(start)}, готово ${relDay(ready, new Date(now))} к ${hm(ready)}` : `Приём был в ${hm(start)}`}
            value={<span className={`chip ${s}`}>{STATUS_RU[s]}</span>}
          />
        </Group>
      )}

      {s !== 'cancelled' && (
        <div className="timeline">
          <Group head="Этапы" i={1}>
            {stages.map((st, i) => {
              const state = i < current ? 'done' : i === current ? 'now' : 'pending'
              return (
                <div key={i} className={state}>
                  <Cell
                    icon={state === 'done' ? <Check size={14} weight="bold" /> : <span style={{ fontSize: 12, fontWeight: 700 }}>{i + 1}</span>}
                    title={st.stage}
                    sub={st.service}
                    value={state === 'now' ? <span className="chip in_work">сейчас</span> : undefined}
                  />
                </div>
              )
            })}
          </Group>
        </div>
      )}

      <Group head="Детали" i={2}>
        <Cell title="Автомобиль" value={booking.car} />
        {booking.plate && <Cell title="Госномер" value={booking.plate} />}
        {booking.services.map(id => (
          <Cell key={id} title={byId(id).name} />
        ))}
        <Cell title={<b>Итого</b>} value={<span className="total">{rub(booking.total)}</span>} />
      </Group>

      <div className="actions inner rise" style={{ ['--i' as string]: 3 }}>
        <a className="btn plain" href={`tel:${STUDIO.phone.replace(/[^\d+]/g, '')}`}>
          Позвонить в студию
        </a>
        {s === 'upcoming' && (
          <button className="btn danger" type="button" onClick={onCancel}>
            Отменить запись
          </button>
        )}
      </div>
    </>
  )
}
