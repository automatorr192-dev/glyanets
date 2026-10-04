import { Cell, Group } from '../components/ui'
import { byId } from '../lib/data'
import { hm, relDay, rub } from '../lib/format'
import type { Booking } from '../lib/store'

type Props = { booking: Booking; now: number; onBookings: () => void; onHome: () => void }

export function Done({ booking, now, onBookings, onHome }: Props) {
  const start = new Date(booking.start)
  return (
    <>
      <div className="done-hero inner">
        <svg className="done-mark" viewBox="0 0 88 88" aria-hidden="true">
          <circle cx="44" cy="44" r="44" />
          <path d="M27 45l11 11 23-24" />
        </svg>
        <h1>Вы записаны</h1>
        <p>
          Ждём {booking.car} {relDay(start, new Date(now))} в {hm(start)}. Запись уже во вкладке «Записи».
        </p>
      </div>

      <Group i={2}>
        {booking.services.map(id => (
          <Cell key={id} title={byId(id).name} />
        ))}
        <Cell title={<b>Итого</b>} value={<span className="total">{rub(booking.total)}</span>} />
      </Group>

      <div className="actions inner rise" style={{ ['--i' as string]: 3 }}>
        <button className="btn" type="button" onClick={onBookings}>Мои записи</button>
        <button className="btn plain" type="button" onClick={onHome}>На главную</button>
      </div>
    </>
  )
}
