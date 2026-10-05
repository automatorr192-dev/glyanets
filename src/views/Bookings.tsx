import { CalendarPlus, CaretRight } from '@phosphor-icons/react'
import { useState } from 'react'
import { Group, NavBar, Segmented } from '../components/ui'
import { byId, inOrder } from '../lib/data'
import { hm } from '../lib/format'
import { status, type Booking, type Status } from '../lib/store'

const MON = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
export const STATUS_RU: Record<Status, string> = {
  in_work: 'В работе',
  upcoming: 'Ждём вас',
  done: 'Готово',
  cancelled: 'Отменена',
}

type Props = { bookings: Booking[]; now: number; onOpen: (id: string) => void; onBook: () => void }

export function Bookings({ bookings, now, onOpen, onBook }: Props) {
  const [tab, setTab] = useState<'next' | 'past'>('next')
  const list = bookings
    .filter(b => {
      const s = status(b, now)
      return tab === 'next' ? s === 'upcoming' || s === 'in_work' : s === 'done' || s === 'cancelled'
    })
    .sort((a, b) => (tab === 'next' ? 1 : -1) * (Date.parse(a.start) - Date.parse(b.start)))

  return (
    <>
      <NavBar title="Записи" large />
      <div className="rise">
        <Segmented
          label="Какие записи показать"
          items={[
            { id: 'next', name: 'Предстоящие' },
            { id: 'past', name: 'История' },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      {list.length ? (
        <Group i={1} key={tab}>
          {list.map(b => {
            const d = new Date(b.start), s = status(b, now)
            return (
              <button key={b.id} type="button" className="cell" onClick={() => onOpen(b.id)} style={{ ['--sep-left' as string]: '72px' }}>
                <span className="date-tile" aria-hidden="true">
                  <b>{d.getDate()}</b>
                  <small>{MON[d.getMonth()]}</small>
                </span>
                <span className="body">
                  <span className="title">{inOrder(b.services).map(id => byId(id).name).join(', ')}</span>
                  <span className="sub">
                    {hm(d)}, {b.car}
                  </span>
                </span>
                <span className={`chip ${s}`}>{STATUS_RU[s]}</span>
                <CaretRight className="chev" size={16} weight="bold" aria-hidden="true" />
              </button>
            )
          })}
        </Group>
      ) : (
        <div className="empty inner rise" style={{ ['--i' as string]: 1 }}>
          <span className="tile">
            <CalendarPlus size={30} weight="fill" />
          </span>
          <h2>{tab === 'next' ? 'Нет предстоящих записей' : 'История пуста'}</h2>
          <p>{tab === 'next' ? 'Выберите услугу и удобное время, это займёт минуту.' : 'Здесь появятся визиты, когда машина побывает у нас.'}</p>
          {tab === 'next' && (
            <button className="btn" type="button" onClick={onBook}>
              Записаться
            </button>
          )}
        </div>
      )}
    </>
  )
}
