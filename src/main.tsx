import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { applyInsets, applyTheme, TG } from './lib/tg'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'

TG?.ready()
TG?.expand()
try {
  TG?.disableVerticalSwipes?.()
} catch {
  /* метод появился в Bot API 7.7 */
}
applyTheme()
applyInsets()
TG?.onEvent('themeChanged', applyTheme)
TG?.onEvent('safeAreaChanged', applyInsets)
TG?.onEvent('contentSafeAreaChanged', applyInsets)
if (!TG) matchMedia('(prefers-color-scheme: light)').addEventListener('change', applyTheme)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
