import { useEffect, useRef, useState, type ReactNode } from 'react'
import { CaretRight, Check } from '@phosphor-icons/react'
import { useMainButton } from '../hooks/useMainButton'
import { useHaptic } from '../hooks/useHaptic'
import { CLASSES, type CarClass } from '../lib/data'
import { rub } from '../lib/format'
import { TG } from '../lib/tg'

type NavProps = { title: string; large?: boolean; sub?: string; right?: ReactNode; hero?: ReactNode }

export function NavBar({ title, large, sub, right, hero }: NavProps) {
  const sentinel = useRef<HTMLDivElement>(null)
  const tall = large || !!hero
  const [compact, setCompact] = useState(!tall)

  useEffect(() => {
    if (!tall || !sentinel.current) return
    const root = sentinel.current.closest('.screen')
    const top = 44 + (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tg-top')) || 0)
    const io = new IntersectionObserver(([e]) => setCompact(!e.isIntersecting), { root, threshold: 0, rootMargin: `-${top}px 0px 0px 0px` })
    io.observe(sentinel.current)
    return () => io.disconnect()
  }, [tall])

  return (
    <>
      <header className={`navbar${compact ? ' compact' : ''}`}>
        {tall ? <span className="small" aria-hidden={!compact}>{title}</span> : <h1 className="small">{title}</h1>}
        {right && <span className="right">{right}</span>}
      </header>
      {hero ? (
        <>
          {hero}
          <div ref={sentinel} style={{ height: 1 }} />
        </>
      ) : large ? (
        <div className="large inner">
          <h1>{title}</h1>
          <div ref={sentinel} style={{ height: 1 }} />
          {sub && <p>{sub}</p>}
        </div>
      ) : (
        <div style={{ height: 52 }} />
      )}
    </>
  )
}

export function Group({ head, foot, children, i = 0, action }: { head?: string; foot?: ReactNode; children: ReactNode; i?: number; action?: ReactNode }) {
  return (
    <section className="group inner rise" style={{ ['--i' as string]: i }}>
      {(head || action) && (
        <div className="group-top">
          {head && <h2 className="group-head">{head}</h2>}
          {action}
        </div>
      )}
      <div className="list">{children}</div>
      {foot && <p className="group-foot">{foot}</p>}
    </section>
  )
}

type CellProps = {
  icon?: ReactNode
  title: ReactNode
  sub?: ReactNode
  value?: ReactNode
  onClick?: () => void
  chevron?: boolean
  checked?: boolean
  href?: string
}

export function Cell({ icon, title, sub, value, onClick, chevron, checked, href }: CellProps) {
  const inner = (
    <>
      {checked !== undefined && <span className="check" aria-hidden="true">{checked && <Check size={16} />}</span>}
      {icon && <span className="tile" aria-hidden="true">{icon}</span>}
      <span className="body">
        <span className="title">{title}</span>
        {sub && <span className="sub">{sub}</span>}
      </span>
      {value !== undefined && <span className="value">{value}</span>}
      {chevron && <CaretRight className="chev" size={16} aria-hidden="true" />}
    </>
  )
  const cls = `cell${icon ? ' has-icon' : ''}`
  if (href) return <a className={cls} href={href} style={{ color: 'inherit', textDecoration: 'none' }}>{inner}</a>
  if (checked !== undefined) return <button type="button" role="checkbox" aria-checked={checked} className={cls} onClick={onClick}>{inner}</button>
  if (onClick) return <button type="button" className={cls} onClick={onClick}>{inner}</button>
  return <div className={cls}>{inner}</div>
}

export function Segmented<T extends string>({ items, value, onChange, label }: { items: { id: T; name: ReactNode; disabled?: boolean }[]; value: T; onChange: (v: T) => void; label: string }) {
  const haptic = useHaptic()
  const idx = Math.max(0, items.findIndex(i => i.id === value))
  return (
    <div className="segmented inner" role="group" aria-label={label}>
      <span className="thumb" aria-hidden="true" style={{ width: `calc((100% - 2px) / ${items.length})`, transform: `translateX(${idx * 100}%)` }} />
      {items.map(i => (
        <button key={i.id} type="button" disabled={i.disabled} aria-pressed={i.id === value} onClick={() => { if (i.id !== value) { haptic.select(); onChange(i.id) } }}>
          {i.name}
        </button>
      ))}
    </div>
  )
}

const SIZE: Record<CarClass, string> = { sedan: 'S', suv: 'M', large: 'L' }

export function ClassPicker({ value, onChange }: { value: CarClass; onChange: (c: CarClass) => void }) {
  const haptic = useHaptic()
  return (
    <div className="classes" role="group" aria-label="Кузов">
      {CLASSES.map(c => (
        <button
          key={c.id}
          type="button"
          aria-pressed={c.id === value}
          className="class"
          onClick={() => {
            if (c.id !== value) {
              haptic.select()
              onChange(c.id)
            }
          }}
        >
          <b>{SIZE[c.id]}</b>
          <small>{c.name}</small>
        </button>
      ))}
    </div>
  )
}

const STEPS = ['Услуги', 'Время', 'Детали']

export function Steps({ at }: { at: number }) {
  return (
    <nav className="steps inner" aria-label={`Шаг ${at + 1} из ${STEPS.length}: ${STEPS[at]}`}>
      <ol>
        {STEPS.map((s, i) => (
          <li key={s} className={i < at ? 'done' : i === at ? 'now' : ''} aria-current={i === at ? 'step' : undefined}>
            {s}
          </li>
        ))}
      </ol>
    </nav>
  )
}

type ActionProps = { text: string; onClick: () => void; active?: boolean; visible: boolean; total?: number; was?: number }

export function BottomAction({ text, onClick, active = true, visible, total, was }: ActionProps) {
  const withTotal = !!total
  useMainButton({ text: withTotal && TG ? `${text} · ${rub(total)}` : text, onClick, active, visible })
  if (!visible) return null
  return (
    <div className="bottom-action">
      {withTotal && (
        <span className="ba-total">
          <small>Итого {!!was && <s>{rub(was)}</s>}</small>
          <b>{rub(total)}</b>
        </span>
      )}
      <button className="btn" type="button" disabled={!active} onClick={onClick}>{text}</button>
    </div>
  )
}

export function Toast({ text }: { text: string | null }) {
  return (
    <div className={`toast${text ? ' show' : ''}`} role="status" aria-live="polite">
      {text}
    </div>
  )
}
