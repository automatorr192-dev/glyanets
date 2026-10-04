import { useEffect, useRef, useState, type ReactNode } from 'react'
import { CaretRight, Check } from '@phosphor-icons/react'
import { useMainButton } from '../hooks/useMainButton'
import { useHaptic } from '../hooks/useHaptic'

export function NavBar({ title, large, sub, right }: { title: string; large?: boolean; sub?: string; right?: ReactNode }) {
  const sentinel = useRef<HTMLDivElement>(null)
  const [compact, setCompact] = useState(!large)

  useEffect(() => {
    if (!large || !sentinel.current) return
    const io = new IntersectionObserver(([e]) => setCompact(!e.isIntersecting), { threshold: 0, rootMargin: '-44px 0px 0px 0px' })
    io.observe(sentinel.current)
    return () => io.disconnect()
  }, [large])

  return (
    <>
      <header className={`navbar${compact ? ' compact' : ''}`}>
        <span className="small" aria-hidden={large && !compact}>{title}</span>
        {right && <span className="right">{right}</span>}
      </header>
      {large ? (
        <div className="large inner">
          <h1>{title}</h1>
          {sub && <p>{sub}</p>}
          <div ref={sentinel} style={{ height: 1 }} />
        </div>
      ) : (
        <div style={{ height: 52 }} />
      )}
    </>
  )
}

export function Group({ head, foot, children, i = 0 }: { head?: string; foot?: ReactNode; children: ReactNode; i?: number }) {
  return (
    <section className="group inner rise" style={{ ['--i' as string]: i }}>
      {head && <h2 className="group-head">{head}</h2>}
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
      {icon && <span className="tile" aria-hidden="true">{icon}</span>}
      <span className="body">
        <span className="title">{title}</span>
        {sub && <span className="sub">{sub}</span>}
      </span>
      {value !== undefined && <span className="value">{value}</span>}
      {checked !== undefined && <span className="check" aria-hidden="true">{checked && <Check size={14} weight="bold" />}</span>}
      {chevron && <CaretRight className="chev" size={16} weight="bold" aria-hidden="true" />}
    </>
  )
  const cls = `cell${icon ? ' has-icon' : ''}`
  if (href) return <a className={cls} href={href} style={{ color: 'inherit', textDecoration: 'none' }}>{inner}</a>
  if (checked !== undefined) return <button type="button" role="checkbox" aria-checked={checked} className={cls} onClick={onClick}>{inner}</button>
  if (onClick) return <button type="button" className={cls} onClick={onClick}>{inner}</button>
  return <div className={cls}>{inner}</div>
}

export function Segmented<T extends string>({ items, value, onChange, label }: { items: { id: T; name: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  const haptic = useHaptic()
  const idx = Math.max(0, items.findIndex(i => i.id === value))
  return (
    <div className="segmented inner" role="group" aria-label={label}>
      <span className="thumb" aria-hidden="true" style={{ width: `calc((100% - 4px) / ${items.length})`, transform: `translateX(${idx * 100}%)` }} />
      {items.map(i => (
        <button key={i.id} type="button" aria-pressed={i.id === value} onClick={() => { if (i.id !== value) { haptic.select(); onChange(i.id) } }}>
          {i.name}
        </button>
      ))}
    </div>
  )
}

export function BottomAction({ text, onClick, active = true, visible }: { text: string; onClick: () => void; active?: boolean; visible: boolean }) {
  useMainButton({ text, onClick, active, visible })
  if (!visible) return null
  return (
    <div className="bottom-action">
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
