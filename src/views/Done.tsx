import { Cell, Group } from '../components/ui'
import { quote } from '../lib/data'
import { hm, relDay, rub } from '../lib/format'
import type { Booking } from '../lib/store'
import { openLink } from '../lib/tg'

type Props = { booking: Booking; now: number; onBookings: () => void; onHome: () => void }

export function Done({ booking, now, onBookings, onHome }: Props) {
  const start = new Date(booking.start)
  const q = quote(booking.services, booking.cls)
  const waiting = booking.status === 'awaiting_payment'
  return (
    <>
      <div className="done-hero inner">
        <svg className="done-mark" viewBox="0 0 88 88" aria-hidden="true">
          <rect width="88" height="88" />
          <path d="M27 45l11 11 23-24" />
        </svg>
        <h1>{waiting ? 'Осталось оплатить' : 'Вы записаны'}</h1>
        <p>
          {waiting
            ? `Внесите предоплату ${rub(booking.prepay ?? 0)} — запись подтвердится сама, время держим 15 минут.`
            : `Ждём ${booking.car} ${relDay(start, new Date(now))} в ${hm(start)}. Запись уже во вкладке «Записи».`}
        </p>
      </div>

      <Group i={2}>
        {q.items.map(i => (
          <Cell key={i.id} title={i.name} value={rub(i.price)} />
        ))}
        {q.discount > 0 && <Cell title="Скидка за комплекс" value={<span className="discount">−{rub(q.discount)}</span>} />}
        <Cell title={<b>Итого</b>} value={<span className="total">{rub(booking.total)}</span>} />
      </Group>

      <div className="actions inner rise" style={{ ['--i' as string]: 3 }}>
        {waiting && booking.invoice && (
          <button className="btn" type="button" onClick={() => openLink(booking.invoice!)}>
            Оплатить {rub(booking.prepay ?? 0)}
          </button>
        )}
        <button className={waiting && booking.invoice ? 'btn plain' : 'btn'} type="button" onClick={onBookings}>
          Мои записи
        </button>
        <button className="btn plain" type="button" onClick={onHome}>На главную</button>
      </div>
    </>
  )
}
