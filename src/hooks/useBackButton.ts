import { useEffect, useRef } from 'react'
import { TG } from '../lib/tg'

export function useBackButton(onBack: () => void, visible: boolean) {
  const handler = useRef(onBack)
  handler.current = onBack

  useEffect(() => {
    if (!TG || !visible) return
    const fire = () => handler.current()
    TG.BackButton.onClick(fire)
    TG.BackButton.show()
    return () => {
      TG!.BackButton.offClick(fire)
      TG!.BackButton.hide()
    }
  }, [visible])
}
