import { BottomAction, Cell, Group, NavBar, Segmented } from '../components/ui'
import { CLASSES, quote, SERVICES, type ServiceId, inOrder } from '../lib/data'
import { duration, rub } from '../lib/format'
import { useHaptic } from '../hooks/useHaptic'
import { ICON } from './Home'
import type { Draft } from '../App'

type Props = { draft: Draft; set: (patch: Partial<Draft>) => void; onNext: () => void; isTop: boolean }

export function Book({ draft, set, onNext, isTop }: Props) {
  const haptic = useHaptic()
  const q = quote(draft.services, draft.cls)
  const toggle = (id: ServiceId) => {
    haptic.select()
    set({ services: draft.services.includes(id) ? draft.services.filter(s => s !== id) : inOrder([...draft.services, id]) })
  }

  return (
    <>
      <NavBar title="Услуги" />
      <div className="rise" style={{ paddingTop: 6 }}>
        <Segmented label="Класс автомобиля" items={CLASSES} value={draft.cls} onChange={cls => set({ cls })} />
      </div>

      <Group i={1}>
        {SERVICES.map(s => (
          <Cell
            key={s.id}
            icon={ICON[s.id]}
            title={s.name}
            sub={`${s.short}. ${duration(s.hours)}`}
            value={rub(s.price[draft.cls])}
            checked={draft.services.includes(s.id)}
            onClick={() => toggle(s.id)}
          />
        ))}
      </Group>

      {draft.services.length > 0 && (
        <Group i={2} foot={q.bundle ? undefined : 'Полировка с керамикой вместе дешевле на 10%.'}>
          <Cell title="Работа займёт" value={duration(q.hours)} />
          {q.discount > 0 && <Cell title="Скидка за комплекс" value={<span className="discount">−{rub(q.discount)}</span>} />}
          <Cell title={<b>Итого</b>} value={<span className="total">{rub(q.total)}</span>} />
        </Group>
      )}

      <BottomAction
        visible={isTop}
        active={draft.services.length > 0}
        text={draft.services.length ? 'Выбрать время' : 'Выберите услугу'}
        onClick={onNext}
      />
    </>
  )
}
