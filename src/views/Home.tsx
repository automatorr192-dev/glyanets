import { Armchair, CalendarCheck, Drop, Percent, Shield, ShieldCheck, Sparkle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { Cell, Group, NavBar } from '../components/ui'
import { LiveActivity } from '../components/LiveActivity'
import { quote, SERVICES, type ServiceId, byId, inOrder } from '../lib/data'
import { duration, hm, relDay, rub } from '../lib/format'
import { status, type Booking } from '../lib/store'
import { userName } from '../lib/tg'

export const ICON: Record<ServiceId, ReactNode> = {
  wash: <Drop size={19} weight="fill" />,
  polish: <Sparkle size={19} weight="fill" />,
  ceramic: <ShieldCheck size={19} weight="fill" />,
  interior: <Armchair size={19} weight="fill" />,
  ppf: <Shield size={19} weight="fill" />,
}

type Props = { bookings: Booking[]; now: number; onBook: (ids: ServiceId[]) => void; onOpen: (id: string) => void }

export function Home({ bookings, now, onBook, onOpen }: Props) {
  const active = bookings.find(b => status(b, now) === 'in_work')
  const next = bookings
    .filter(b => status(b, now) === 'upcoming')
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start))[0]
  const combo = quote(['polish', 'ceramic'], 'sedan')

  return (
    <>
      <NavBar title="Глянец" large sub="Детейлинг у метро ЦСКА" right={<span className="avatar" aria-label={userName()}>{userName()[0]}</span>} />

      {active && <LiveActivity booking={active} now={now} onOpen={() => onOpen(active.id)} />}

      {next && (
        <Group i={1}>
          <Cell
            icon={<CalendarCheck size={19} weight="fill" />}
            title={`Ждём вас ${relDay(new Date(next.start), new Date(now))} в ${hm(new Date(next.start))}`}
            sub={inOrder(next.services).map(id => byId(id).name).join(', ')}
            chevron
            onClick={() => onOpen(next.id)}
          />
        </Group>
      )}

      <Group head="Услуги" i={2} foot="Цены для седана. Если кузову нужно больше работы, скажем на приёмке, до начала, а не после.">
        {SERVICES.map(s => (
          <Cell
            key={s.id}
            icon={ICON[s.id]}
            title={s.name}
            sub={`от ${rub(s.price.sedan)}, ${duration(s.hours)}`}
            chevron
            onClick={() => onBook([s.id])}
          />
        ))}
      </Group>

      <Group head="Вместе дешевле" i={3}>
        <Cell
          icon={<Percent size={19} weight="bold" />}
          title="Полировка и керамика"
          sub="Скидка 10% на комплекс"
          value={rub(combo.total)}
          chevron
          onClick={() => onBook(['polish', 'ceramic'])}
        />
      </Group>
    </>
  )
}
