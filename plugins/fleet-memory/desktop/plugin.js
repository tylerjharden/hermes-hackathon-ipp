import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ink = '#1c1915'
const mute = '#6b645b'
const line = '#e4dccf'

const twoLines = {
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  lineHeight: '1.35',
  maxHeight: '2.7em',
  wordBreak: 'normal',
  overflowWrap: 'break-word',
  minWidth: 0,
}

function shownRecalls(rows) {
  const seen = new Set()
  const out = []
  for (const row of rows || []) {
    const key = row.id != null ? String(row.id) : `${row.at}|${row.source}|${row.query}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(row)
  }
  return out
}

function MemoryPane(props) {
  const [summary, setSummary] = useState({
    counts: { notes: 0, recalls: 0, turns: 0 },
    recalls: [],
    notes: [],
    data_label: 'local store',
    status: { line: 'Watching the local store', at: '' },
    error: '',
  })
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(clock)
  }, [])

  useEffect(() => {
    let alive = true
    const load = () => {
      props.rest(`/summary?t=${Date.now()}`, { cache: 'no-store' }).then((body) => {
        if (alive) setSummary(body)
      }).catch((err) => {
        if (alive) {
          setSummary((prev) => ({
            ...prev,
            error: err && err.message ? err.message : 'Gateway route unavailable',
          }))
        }
      })
    }
    load()
    const timer = setInterval(load, 500)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const counts = summary.counts || { notes: 0, recalls: 0, turns: 0 }
  const recalls = shownRecalls(summary.recalls)
  const notes = summary.notes || []
  const age = summary.status && summary.status.at
    ? Math.max(0, Math.round((now - Date.parse(summary.status.at)) / 1000))
    : 0

  return jsxs('div', {
    style: { color: ink, font: '14px/1.4 "Iowan Old Style", Palatino, serif' },
    children: [
      jsxs('header', {
        style: { display: 'flex', justifyContent: 'space-between', gap: 8 },
        children: [
          jsx('h1', { style: { fontSize: 18, margin: 0 }, children: 'Fleet memory' }),
          jsx('span', {
            style: { color: mute, font: '12px/1.4 ui-monospace, monospace' },
            children: summary.data_label || 'local store',
          }),
        ],
      }),
      jsx('p', {
        style: { color: mute, overflowWrap: 'break-word', wordBreak: 'normal', margin: '8px 0' },
        children: `${(summary.status && summary.status.line) || 'Watching the local store'} · ${age}s`,
      }),
      summary.error ? jsx('p', { style: { color: '#991b1b' }, children: summary.error }) : null,
      jsx('p', { children: `${counts.notes} notes · ${counts.recalls} recalls · ${counts.turns} turns` }),
      jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Recall cards' }),
      recalls.length
        ? recalls.map((recall) => jsxs('article', {
            style: { borderTop: `1px solid ${line}`, padding: '8px 0' },
            children: [
              jsx('div', {
                style: { color: mute, font: '12px/1.4 ui-monospace, monospace', whiteSpace: 'nowrap' },
                children: recall.label || (recall.source === 'auto' ? 'auto-recall' : 'recalled'),
              }),
              recall.show_query === false
                ? null
                : jsx('strong', { style: twoLines, children: recall.query_text || recall.query }),
              (recall.hits || []).map((hit) => jsxs('div', {
                style: { background: '#fff', border: `1px solid ${line}`, padding: 8, marginTop: 6 },
                children: [
                  jsx('strong', { style: twoLines, children: hit.title_text || hit.title }),
                  jsx('div', { style: { color: mute, marginTop: 4 }, children: `score ${hit.score}` }),
                  jsx('p', { style: { margin: '4px 0 0', overflowWrap: 'break-word' }, children: hit.snippet }),
                ],
              }, `${recall.id}-${hit.id}`)),
            ],
          }, String(recall.id)))
        : jsx('p', { style: { color: mute }, children: 'No recalls yet.' }),
      jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Timeline' }),
      notes.length
        ? jsx('ul', {
            style: { listStyle: 'none', padding: 0, margin: 0 },
            children: notes.map((note) => jsxs('li', {
              style: { padding: '6px 0', borderTop: `1px solid ${line}` },
              children: [
                jsx('div', { style: twoLines, children: note.title }),
                jsx('div', { style: { color: mute }, children: note.updated_at }),
              ],
            }, note.id)),
          })
        : jsx('p', { style: { color: mute }, children: 'Local store is empty.' }),
    ],
  })
}

export default {
  id: 'fleet-memory',
  name: 'Fleet memory',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Fleet memory',
      data: { placement: 'right', width: '320px' },
      render: () => jsx(MemoryPane, { rest: (path, options) => ctx.rest(path, options) }),
    })
  },
}
