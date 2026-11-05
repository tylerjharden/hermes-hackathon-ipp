import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

function Badge(props) {
  const prod = props.env === 'prod'
  return jsx('span', {
    className: prod ? 'badge badge-prod' : 'badge badge-dev',
    children: prod ? 'prod' : 'dev',
  })
}

function GuardPane(props) {
  const [summary, setSummary] = useState({
    env: 'dev',
    routine_allowlist: [],
    events: [],
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
            env: 'dev',
            routine_allowlist: [],
            events: [],
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

  const events = summary.events || []
  const allow = summary.routine_allowlist || []
  return jsxs('div', {
    className: 'pane',
    children: [
      jsxs('header', {
        className: 'pane-head',
        children: [
          jsx('h1', { children: 'Odoo prod guard' }),
          jsx(Badge, { env: summary.env }),
          jsx('span', { className: 'muted', children: summary.backend === 'live' ? 'live' : 'fixture' }),
        ],
      }),
      summary.error
        ? jsx('p', { className: 'error', children: summary.error })
        : null,
      jsx('h2', { children: 'Environment' }),
      jsx('p', { children: summary.env === 'prod' ? 'Production writes are gated.' : 'Dev writes are logged and not gated.' }),
      jsx('h2', { children: 'Routine allowlist' }),
      allow.length
        ? jsx('ul', {
            children: allow.map((item) => jsx('li', { children: item }, item)),
          })
        : jsx('p', { className: 'muted', children: 'No routine writes. Every production write asks for approval.' }),
      jsx('h2', { children: 'Recent gated calls' }),
      events.length
        ? jsx('ul', {
            className: 'events',
            children: events.map((event) => jsxs('li', {
              children: [
                jsx('span', { className: 'decision', children: event.decision }),
                jsx('span', { children: `${event.model}.${event.method}` }),
                jsx('span', { className: 'muted', children: event.at }),
              ],
            }, `${event.at}-${event.model}-${event.method}`)),
          })
        : jsx('p', { className: 'muted', children: 'No gated calls yet.' }),
    ],
  })
}

export default {
  id: 'odoo-prod-guard',
  name: 'Odoo prod guard',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Odoo guard',
      data: { placement: 'right', width: '320px' },
      render: () => jsx(GuardPane, { rest: (path, options) => ctx.rest(path, options) }),
    })
  },
}
