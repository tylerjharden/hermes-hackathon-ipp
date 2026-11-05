import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

function MemoryPane(props) {
  const [summary, setSummary] = useState({
    counts: { notes: 0, recalls: 0, turns: 0 },
    recalls: [],
    error: '',
  })

  useEffect(() => {
    let alive = true
    const load = () => {
      props.rest('/summary').then((body) => {
        if (alive) setSummary(body)
      }).catch((err) => {
        if (alive) {
          setSummary({
            counts: { notes: 0, recalls: 0, turns: 0 },
            recalls: [],
            error: err && err.message ? err.message : 'Gateway route unavailable',
          })
        }
      })
    }
    load()
    const timer = setInterval(load, 3000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const counts = summary.counts || { notes: 0, recalls: 0, turns: 0 }
  const recalls = summary.recalls || []
  const noun = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
  return jsxs('div', {
    className: 'pane',
    children: [
      jsxs('header', {
        className: 'pane-head',
        children: [
          jsx('h1', { children: 'Fleet memory' }),
          jsx('span', { className: 'muted', children: summary.backend === 'notion' ? 'notion' : 'fixture' }),
        ],
      }),
      summary.error ? jsx('p', { className: 'error', children: summary.error }) : null,
      jsx('h2', { children: 'Store' }),
      jsx('p', {
        children: `${noun(counts.notes, 'note')}, ${noun(counts.recalls, 'recall')}, ${noun(counts.turns, 'turn')}`,
      }),
      jsx('h2', { children: 'Recent recalls' }),
      recalls.length
        ? jsx('ul', {
            children: recalls.map((recall) => jsxs('li', {
              children: [
                jsx('span', { children: recall.query }),
                jsx('span', { className: 'muted', children: (recall.hit_ids || []).join(', ') }),
              ],
            }, `${recall.at}-${recall.query}`)),
          })
        : jsx('p', { className: 'muted', children: 'No recalls yet.' }),
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
