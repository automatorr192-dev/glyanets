import { Armchair, CalendarCheck, Drop, Shield, ShieldCheck, Sparkle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { Cell, ClassPicker, Group, NavBar } from '../components/ui'
import { LiveActivity } from '../components/LiveActivity'
import { quote, SERVICES, STUDIO, type CarClass, type ServiceId, byId, inOrder } from '../lib/data'
import { duration, hm, relDay, rub } from '../lib/format'
import { status, type Booking } from '../lib/store'
import { userName } from '../lib/tg'

export const ICON: Record<ServiceId, ReactNode> = {
  wash: <Drop size={18} />,
  polish: <Sparkle size={18} />,
  ceramic: <ShieldCheck size={18} />,
  interior: <Armchair size={18} />,
  ppf: <Shield size={18} />,
}

type Props = {
  bookings: Booking[]
  now: number
  cls: CarClass
  onClass: (cls: CarClass) => void
  onBook: (ids: ServiceId[]) => void
  onOpen: (id: string) => void
}

export function Home({ bookings, now, cls, onClass, onBook, onOpen }: Props) {
  const active = bookings.find(b => status(b, now) === 'in_work')
  const next = bookings
    .filter(b => status(b, now) === 'upcoming')
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start))[0]
  const combo = quote(['polish', 'ceramic'], cls)

  const hero = (
    <section className="hero">
      <figure className="hero-shot" aria-hidden="true">
        <img src="./hero-car.webp" alt="" width="1600" height="1000" decoding="async" fetchPriority="high" />
      </figure>
      <div className="hero-copy inner">
        <h1 className="hero-title">Глянец</h1>
        <p className="hero-text">Детейлинг у м. {STUDIO.metro}: мойка, полировка, керамика и плёнка. Запишитесь за минуту и следите за машиной, пока она у нас.</p>
        <button className="btn hero-cta" type="button" onClick={() => onBook([])}>
          Записаться
        </button>
      </div>
    </section>
  )

  return (
    <>
      <NavBar title="Глянец" hero={hero} right={<span className="avatar" aria-label={userName()}>{userName()[0]}</span>} />

      {active && <LiveActivity booking={active} now={now} onOpen={() => onOpen(active.id)} />}

      {next && (
        <Group i={1}>
          <Cell
            icon={<CalendarCheck size={18} />}
            title={`Ждём вас ${relDay(new Date(next.start), new Date(now))} в ${hm(new Date(next.start))}`}
            sub={inOrder(next.services).map(id => byId(id).name).join(', ')}
            chevron
            onClick={() => onOpen(next.id)}
          />
        </Group>
      )}

      <section className="group inner rise" style={{ ['--i' as string]: 2 }}>
        <h2 className="group-head">Кузов</h2>
        <ClassPicker value={cls} onChange={onClass} />
        <p className="group-foot">Цены ниже посчитаны для выбранного кузова. Если машине нужно больше работы, скажем на приёмке, до начала.</p>
      </section>

      <Group head="Услуги" i={3}>
        {SERVICES.map(s => (
          <button key={s.id} type="button" className="service" onClick={() => onBook([s.id])}>
            <span className="service-name">{s.name}</span>
            <span className="service-price">{rub(s.price[cls])}</span>
            <span className="service-sub">
              {duration(s.hours)}. {s.short}
            </span>
          </button>
        ))}
      </Group>

      <button type="button" className="bundle inner rise" style={{ ['--i' as string]: 4 }} onClick={() => onBook(['polish', 'ceramic'])}>
        <span className="bundle-off">−10%</span>
        <span className="bundle-name">Полировка и керамика вместе</span>
        <span className="bundle-price">
          <s>{rub(combo.subtotal)}</s>
          <b>{rub(combo.total)}</b>
        </span>
      </button>
    </>
  )
}
