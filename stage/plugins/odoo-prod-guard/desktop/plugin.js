import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ink = '#1c1915'
const mute = '#6b645b'
const line = '#e4dccf'

function tone(decision) {
  if (decision === 'allowed') return ['#d1fae5', '#065f46']
  if (decision === 'approve') return ['#ffedd5', '#9a3412']
  if (decision === 'warn') return ['#fef3c7', '#92400e']
  return ['#e7e5e4', ink]
}

function badge(label, colors) {
  return jsx('span', {
    style: {
      display: 'inline-block',
      borderRadius: 999,
      padding: '2px 8px',
      background: colors[0],
      color: colors[1],
      font: '12px/1.4 ui-monospace, monospace',
    },
    children: label,
  })
}

function GuardPane(props) {
  const [summary, setSummary] = useState({
    env: 'dev',
    routine_allowlist: [],
    events: [],
    data_label: 'demo data',
    status: { line: 'Watching the production gate', at: '' },
    error: '',
  })
  const [now, setNow] = useState(Date.now())
  const [busy, setBusy] = useState(0)

  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(clock)
  }, [])

  useEffect(() => {
    let alive = true
    const load = () => {
      props.rest('/summary').then((body) => {
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
    const timer = setInterval(load, 1000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const events = summary.events || []
  const allow = summary.routine_allowlist || []
  const passing = events.find((event) => event.decision === 'allowed')
  const gated = events.find((event) => event.decision === 'approve')
  const age = summary.status && summary.status.at
    ? Math.max(0, Math.round((now - Date.parse(summary.status.at)) / 1000))
    : 0

  function decide(event, decision) {
    setBusy(event.id)
    props.rest('/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: event.id, decision }),
    }).then(() => setBusy(0)).catch(() => setBusy(0))
  }

  function card(event, title) {
    if (!event) {
      return jsx('p', { style: { color: mute }, children: `No ${title} yet.` })
    }
    return jsxs('article', {
      style: { border: `1px solid ${line}`, background: '#fff', padding: 8, marginBottom: 8 },
      children: [
        jsxs('div', {
          style: { display: 'flex', justifyContent: 'space-between', gap: 8 },
          children: [
            jsx('strong', { children: title }),
            badge(event.decision, tone(event.decision)),
          ],
        }),
        jsx('div', { children: `${event.model}.${event.method}` }),
        jsx('pre', {
          style: { whiteSpace: 'pre-wrap', font: '12px/1.4 ui-monospace, monospace', margin: '6px 0' },
          children: event.preview || event.message,
        }),
        event.audit
          ? jsx('p', { children: event.audit })
          : jsxs('div', {
              style: { display: 'flex', gap: 8 },
              children: [
                jsx('button', { type: 'button', disabled: busy === event.id, onClick: () => decide(event, 'approve'), children: 'Approve' }),
                jsx('button', { type: 'button', disabled: busy === event.id, onClick: () => decide(event, 'deny'), children: 'Deny' }),
              ],
            }),
      ],
    })
  }

  return jsxs('div', {
    style: { color: ink, font: '14px/1.4 "Iowan Old Style", Palatino, serif' },
    children: [
      jsxs('header', {
        style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
        children: [
          jsx('h1', { style: { fontSize: 18, margin: 0 }, children: 'Odoo prod guard' }),
          badge(summary.env === 'prod' ? 'prod' : 'dev', summary.env === 'prod' ? ['#ffedd5', '#9a3412'] : ['#d1fae5', '#065f46']),
        ],
      }),
      jsx('p', { style: { color: mute }, children: `${summary.data_label || 'demo data'} · ${(summary.status && summary.status.line) || 'Watching the production gate'} · ${age}s` }),
      jsx('p', { style: { color: mute }, children: 'Approve and Deny mark the audit trail. They do not run the write.' }),
      summary.error ? jsx('p', { style: { color: '#991b1b' }, children: summary.error }) : null,
      jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Allowlist beside the gate' }),
      card(passing, 'Allowlisted write'),
      card(gated, 'Gated write'),
      jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Routine allowlist' }),
      allow.length
        ? jsx('ul', { children: allow.map((item) => jsx('li', { children: item }, item)) })
        : jsx('p', { style: { color: mute }, children: 'No routine writes. Every production write asks for approval.' }),
      jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Live call log' }),
      events.length
        ? jsx('ul', {
            style: { listStyle: 'none', padding: 0, margin: 0 },
            children: events.map((event) => jsxs('li', {
              style: { padding: '8px 0', borderTop: `1px solid ${line}` },
              children: [
                badge(event.decision, tone(event.decision)),
                jsx('div', { children: `${event.model}.${event.method}` }),
                jsx('div', { style: { color: mute }, children: event.audit || event.at }),
              ],
            }, String(event.id))),
          })
        : jsx('p', { style: { color: mute }, children: 'No gated calls yet.' }),
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
