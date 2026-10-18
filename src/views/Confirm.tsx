import { ArrowCounterClockwise, CreditCard, Wrench } from '@phosphor-icons/react'
import { BottomAction, Cell, Group, NavBar, Steps } from '../components/ui'
import { CLASSES, quote, readyAt } from '../lib/data'
import { hm, plural, relDay, rub } from '../lib/format'
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

const cap = (s: string) => s[0].toUpperCase() + s.slice(1)

type Props = {
  draft: Draft
  set: (patch: Partial<Draft>) => void
  now: number
  onSubmit: () => void
  onEditTime: () => void
  onEditServices: () => void
  isTop: boolean
  prepay: number
}

export function Confirm({ draft, set, now, onSubmit, onEditTime, onEditServices, isTop, prepay }: Props) {
  const haptic = useHaptic()
  const q = quote(draft.services, draft.cls)
  const start = startOf(draft, now)
  const ready = readyAt(start, q.hours)
  const digits = draft.phone.replace(/\D/g, '').length
  const phoneOk = digits === 11
  const carOk = draft.car.trim().length > 1
  const valid = carOk && phoneOk
  const missing = [!carOk && 'машину', !phoneOk && 'телефон'].filter(Boolean).join(' и ')
  const phoneError = digits > 1 && !phoneOk ? `Не хватает ${11 - digits} ${plural(11 - digits, 'цифры', 'цифр', 'цифр')}` : null
  const edit = (go: () => void) => (
    <button type="button" className="edit" onClick={() => { haptic.tap(); go() }}>
      Изменить
    </button>
  )

  const share = async () => {
    haptic.tap()
    const phone = await requestPhone()
    if (phone) set({ phone: maskPhone(phone) })
  }

  return (
    <>
      <NavBar title="Запись" />
      <Steps at={2} />

      <Group head="Визит" i={0} action={edit(onEditTime)}>
        <div className="visit">
          <b>{cap(relDay(start, new Date(now)))}, {draft.time}</b>
          <span>Готово {relDay(ready, new Date(now))} к {hm(ready)}</span>
        </div>
      </Group>

      <Group head="Услуги" i={1} action={edit(onEditServices)}>
        <Cell title="Кузов" value={CLASSES.find(c => c.id === draft.cls)!.name} />
        {q.items.map(i => (
          <Cell key={i.id} title={i.name} value={rub(i.price)} />
        ))}
        {q.discount > 0 && <Cell title="Скидка за комплекс" value={<span className="discount">−{rub(q.discount)}</span>} />}
        <div className="sum">
          <span>Итого</span>
          <b>{rub(q.total)}</b>
        </div>
      </Group>

      <Group head="Автомобиль" i={2} foot="Номер охрана сверит на въезде; без него спросит на месте.">
        <div className="field">
          <label htmlFor="car">Машина</label>
          <input id="car" value={draft.car} onChange={e => set({ car: e.target.value })} placeholder="Марка и модель" autoComplete="off" />
        </div>
        <div className="field">
          <label htmlFor="plate">
            Госномер <small>необязательно</small>
          </label>
          <input id="plate" value={draft.plate} onChange={e => set({ plate: e.target.value.toUpperCase() })} placeholder="А 000 АА 777" autoComplete="off" />
        </div>
      </Group>

      <Group
        head="Контакт"
        i={3}
        foot={
          valid
            ? 'Нажимая «Записаться», вы соглашаетесь на обработку персональных данных для связи по этой записи.'
            : `Чтобы записаться, укажите ${missing}.`
        }
      >
        <div className="field">
          <label htmlFor="name">
            Имя <small>необязательно</small>
          </label>
          <input id="name" value={draft.name} onChange={e => set({ name: e.target.value })} placeholder="Как к вам обращаться" autoComplete="given-name" />
        </div>
        <div className="field">
          <label htmlFor="phone">Телефон</label>
          <input
            id="phone"
            type="tel"
            inputMode="tel"
            value={draft.phone}
            onChange={e => set({ phone: maskPhone(e.target.value) })}
            placeholder="+7 999 000-00-00"
            autoComplete="tel"
            aria-invalid={!!phoneError}
            aria-describedby={phoneError ? 'phone-error' : undefined}
          />
          {phoneError && (
            <span className="error" id="phone-error">
              {phoneError}
            </span>
          )}
        </div>
        {TG && !phoneOk && (
          <button type="button" className="link-row" onClick={share}>
            Взять номер из Telegram
          </button>
        )}
      </Group>

      <ul className="assure inner rise" style={{ ['--i' as string]: 4 }}>
        <li>
          <CreditCard size={18} aria-hidden="true" />
          {prepay > 0
            ? `Предоплата ${prepay}% по СБП или картой, остальное — в студии после приёмки.`
            : 'Оплата в студии после приёмки работы, предоплаты нет.'}
        </li>
        <li>
          <Wrench size={18} aria-hidden="true" />
          Если на приёмке найдём больше работы, согласуем цену до начала.
        </li>
        <li>
          <ArrowCounterClockwise size={18} aria-hidden="true" />
          Отменить запись можно во вкладке «Записи» в любой момент.
        </li>
      </ul>

      <BottomAction visible={isTop} active={valid} text="Записаться" total={q.total} onClick={onSubmit} />
    </>
  )
}
