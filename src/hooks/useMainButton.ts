import { useEffect, useRef } from 'react'
import { TG } from '../lib/tg'

type Options = { text: string; visible: boolean; active?: boolean; onClick: () => void }

export function useMainButton({ text, visible, active = true, onClick }: Options) {
  const handler = useRef(onClick)
  handler.current = onClick

  useEffect(() => {
    if (!TG || !visible) return
    const css = getComputedStyle(document.documentElement)
    const fire = () => {
      if (active) handler.current()
    }
    TG.MainButton.setParams({
      text,
      color: active ? css.getPropertyValue('--tint').trim() : css.getPropertyValue('--cell-2').trim(),
      text_color: active ? css.getPropertyValue('--tint-ink').trim() : css.getPropertyValue('--label-2-solid').trim(),
      is_active: active,
      is_visible: true,
    })
    TG.MainButton.onClick(fire)
    return () => {
      TG!.MainButton.offClick(fire)
      TG!.MainButton.hide()
    }
  }, [text, visible, active])
}
