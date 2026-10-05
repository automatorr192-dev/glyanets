import { Car } from '@phosphor-icons/react'
import { byId, inOrder, STAGES } from '../lib/data'
import { hm, relDay } from '../lib/format'
import { progress, type Booking } from '../lib/store'

export function stagesOf(b: Booking) {
  return inOrder(b.services).flatMap(id => STAGES[id].map(stage => ({ service: byId(id).name, stage })))
}

export function LiveActivity({ booking, now, onOpen }: { booking: Booking; now: number; onOpen?: () => void }) {
  const p = progress(booking, now)
  const stages = stagesOf(booking)
  const current = Math.min(stages.length - 1, Math.floor(p * stages.length))
  const ready = new Date(booking.ready)
  const Tag = onOpen ? 'button' : 'div'

  return (
    <Tag type={onOpen ? 'button' : undefined} className="live inner rise" onClick={onOpen} aria-label={`В работе: ${booking.car}, ${Math.round(p * 100)} процентов`}>
      <div className="live-top">
        <span className="live-icon" aria-hidden="true">
          <Car size={26} weight="fill" />
        </span>
        <div className="live-text">
          <span className="live-state">
            <i aria-hidden="true" /> В работе · {Math.round(p * 100)}%
          </span>
          <b className="live-car">{booking.car}</b>
          <span className="live-step">
            {stages[current].service}: {stages[current].stage.toLowerCase()}
          </span>
        </div>
        <div className="live-eta">
          <small>Готово</small>
          <b>{hm(ready)}</b>
          <small>{relDay(ready, new Date(now))}</small>
        </div>
      </div>
      <ol className="live-steps" aria-hidden="true">
        {stages.map((_, i) => (
          <li key={i} className={i < current ? 'done' : i === current ? 'now' : ''} />
        ))}
      </ol>
    </Tag>
  )
}
