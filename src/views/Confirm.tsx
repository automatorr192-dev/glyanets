import { CalendarBlank } from '@phosphor-icons/react'
import { BottomAction, Cell, Group, NavBar } from '../components/ui'
import { quote, readyAt } from '../lib/data'
import { hm, relDay, rub } from '../lib/format'
import { requestPhone, TG } from '../lib/tg'
import { useHaptic } from '../hooks/useHaptic'
import { startOf } from './Time'
import type { Draft } from '../App'

export function maskPhone(raw: string) {
  let d = raw.replace(/\D/g, '')
  if (d.startsWith('8')) d = '7' + d.slice(1)
  if (d && !d.startsWith('7')) d = '7' + d
  d = d.slice(0, 11)
  const p = [d.slice(1, 4), d.slice(4, 7), d.slice(7, 9), d.slice(9, 11)]
  return d ? '+7' + (p[0] ? ' ' + p[0] : '') + (p[1] ? ' ' + p[1] : '') + (p[2] ? '-' + p[2] : '') + (p[3] ? '-' + p[3] : '') : ''
}

type Props = { draft: Draft; set: (patch: Partial<Draft>) => void; now: number; onSubmit: () => void; isTop: boolean }

export function Confirm({ draft, set, now, onSubmit, isTop }: Props) {
  const haptic = useHaptic()
  const q = quote(draft.services, draft.cls)
  const start = startOf(draft, now)
  const ready = readyAt(start, q.hours)
  const phoneOk = draft.phone.replace(/\D/g, '').length === 11
  const valid = draft.car.trim().length > 1 && phoneOk

  const share = async () => {
    haptic.tap()
    const phone = await requestPhone()
    if (phone) set({ phone: maskPhone(phone) })
  }

  return (
    <>
      <NavBar title="Подтверждение" />

      <Group i={0}>
        <Cell
          icon={<CalendarBlank size={19} weight="fill" />}
          title={`${relDay(start, new Date(now))[0].toUpperCase() + relDay(start, new Date(now)).slice(1)}, ${draft.time}`}
          sub={`Готово ${relDay(ready, new Date(now))} к ${hm(ready)}`}
        />
      </Group>

      <Group head="Услуги" i={1}>
        {q.items.map(i => (
          <Cell key={i.id} title={i.name} value={rub(i.price)} />
        ))}
        {q.discount > 0 && <Cell title="Скидка за комплекс" value={<span className="discount">−{rub(q.discount)}</span>} />}
        <Cell title={<b>Итого</b>} value={<span className="total">{rub(q.total)}</span>} />
      </Group>

      <Group head="Автомобиль" i={2} foot="Номер нужен охране на въезде.">
        <div className="field">
          <label htmlFor="car">Машина</label>
          <input id="car" value={draft.car} onChange={e => set({ car: e.target.value })} placeholder="Марка и модель" autoComplete="off" />
        </div>
        <div className="field">
          <label htmlFor="plate">Госномер</label>
          <input id="plate" value={draft.plate} onChange={e => set({ plate: e.target.value.toUpperCase() })} placeholder="Госномер" autoComplete="off" />
        </div>
      </Group>

      <Group
        head="Контакт"
        i={3}
        foot={
          valid
            ? 'Нажимая «Записаться», вы соглашаетесь на обработку персональных данных для связи по этой записи.'
            : 'Чтобы записаться, укажите автомобиль и телефон.'
        }
      >
        <div className="field">
          <label htmlFor="name">Имя</label>
          <input id="name" value={draft.name} onChange={e => set({ name: e.target.value })} placeholder="Имя" autoComplete="given-name" />
        </div>
        <div className="field">
          <label htmlFor="phone">Телефон</label>
          <input
            id="phone"
            type="tel"
            inputMode="tel"
            value={draft.phone}
            onChange={e => set({ phone: maskPhone(e.target.value) })}
            placeholder="+7 999 000 00 00"
            autoComplete="tel"
          />
        </div>
        {TG && !phoneOk && <Cell title={<span style={{ color: 'var(--tint)' }}>Взять номер из Telegram</span>} onClick={share} />}
      </Group>

      <BottomAction visible={isTop} active={valid} text={`Записаться · ${rub(q.total)}`} onClick={onSubmit} />
    </>
  )
}
