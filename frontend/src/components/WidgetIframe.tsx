import { useEffect, useRef, useState } from 'react'

const RESIZE_DELAYS_MS = [50, 200, 600, 1500]
const MIN_HEIGHT = 80

function buildSrcDoc(innerHtml: string): string {
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>
    body { margin: 0; padding: 12px; background: #1f2937;
           color: #e5e7eb; font-family: ui-sans-serif, system-ui, sans-serif; }
    .widget-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #f3f4f6; }
    table { border-collapse: collapse; width: 100%; font-size: 13px; }
    th, td { border: 1px solid #374151; padding: 6px 10px; text-align: left; }
    th { background: #111827; }
    canvas { max-width: 100%; }
  </style>
</head>
<body>
  ${innerHtml}
  <script>
    function postHeight() {
      parent.postMessage({ type: 'widget-height', height: document.body.scrollHeight }, '*');
    }
    window.addEventListener('load', postHeight);
    if (window.ResizeObserver) new ResizeObserver(postHeight).observe(document.body);
    ${RESIZE_DELAYS_MS.map(d => `setTimeout(postHeight, ${d});`).join('\n    ')}
  </script>
</body>
</html>`
}

export function WidgetIframe({ html }: { html: string }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(160)

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.source !== ref.current?.contentWindow) return
      if (event.data?.type === 'widget-height') {
        setHeight(Math.max(MIN_HEIGHT, Math.ceil(event.data.height)))
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  return (
    <iframe
      ref={ref}
      title="Data widget"
      sandbox="allow-scripts"
      srcDoc={buildSrcDoc(html)}
      style={{ width: '100%', height, border: 'none', borderRadius: 12 }}
    />
  )
}
