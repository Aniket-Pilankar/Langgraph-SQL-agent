import type { WidgetBlock as WidgetBlockData } from '../hooks/useChat'
import { WidgetSkeleton } from './WidgetSkeleton'
import { WidgetIframe } from './WidgetIframe'

export function WidgetBlock({ block }: { block: WidgetBlockData }) {
  const isReady = block.status === 'ready' && Boolean(block.html)
  return <div className="widget-block">{isReady ? <WidgetIframe html={block.html} /> : <WidgetSkeleton />}</div>
}
