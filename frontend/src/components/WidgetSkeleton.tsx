import { useEffect, useState } from 'react'
import './WidgetSkeleton.css'

const LOADING_MESSAGES = ['Generating chart…', 'Preparing visualization…', 'Rendering data…']
const ROTATE_INTERVAL_MS = 2000
const BAR_HEIGHTS = ['40%', '70%', '55%', '85%', '60%']

export function WidgetSkeleton() {
  const [msgIndex, setMsgIndex] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setMsgIndex(i => (i + 1) % LOADING_MESSAGES.length), ROTATE_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="widget-skeleton">
      <div className="widget-skeleton__bars">
        {BAR_HEIGHTS.map((height, i) => (
          <span key={i} className="widget-skeleton__bar" style={{ height }} />
        ))}
      </div>
      <p className="widget-skeleton__label">{LOADING_MESSAGES[msgIndex]}</p>
    </div>
  )
}
