import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'
import { Button, host, useValue } from '@hermes/plugin-sdk'

const ink = '#1c1915'
const paper = '#f7f4ee'
const line = '#e4dccf'
const mute = '#6b645b'

function chipStyle(label) {
  const tones = {
    triage: ['#e7e5e4', ink],
    delegated: ['#dbeafe', '#1e3a8a'],
    'awaiting-worker': ['#fef3c7', '#92400e'],
    'needs-approval': ['#ffedd5', '#9a3412'],
    done: ['#d1fae5', '#065f46'],
    billing: ['#ede9fe', '#5b21b6'],
    ops: ['#dbeafe', '#1e3a8a'],
    sales: ['#fce7f3', '#9d174d'],
    high: ['#fee2e2', '#991b1b'],
    normal: ['#e7e5e4', ink],
  }
  const tone = tones[label] || tones.triage
  return {
    display: 'inline-block',
    borderRadius: 999,
    padding: '2px 8px',
    marginRight: 6,
    marginBottom: 4,
    background: tone[0],
    color: tone[1],
    font: '12px/1.4 ui-monospace, monospace',
  }
}

function FrontDoor(props) {
  const profile = useValue(host.state.profile)
  const [board, setBoard] = useState({
    data_label: 'demo data',
    status: { line: 'Watching the inbox', at: '' },
    threads: [],
    focus: '',
    selected: null,
    history: [],
    error: '',
  })
  const [picked, setPicked] = useState('')
  const [now, setNow] = useState(Date.now())
  const [busy, setBusy] = useState('')

  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(clock)
  }, [])

  useEffect(() => {
    let alive = true
    const load = () => {
      const query = picked ? `?thread_id=${encodeURIComponent(picked)}` : ''
      props.rest(`/board${query}`).then((body) => {
        if (alive) setBoard(body)
      }).catch((err) => {
        if (alive) {
          setBoard((prev) => ({
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
  }, [picked])

  const threads = board.threads || []
  const selected = board.selected
  const classification = selected && selected.classification
  const age = board.status && board.status.at
    ? Math.max(0, Math.round((now - Date.parse(board.status.at)) / 1000))
    : 0

  function decide(decision) {
    const threadId = (selected && selected.thread_id) || picked
    if (!threadId) return
    const actor = typeof profile === 'string' && profile.trim() ? profile.trim() : 'operator'
    setBusy(decision)
    props.rest('/decision', {
      method: 'POST',
      body: { thread_id: threadId, decision, actor },
    }).then((body) => {
      setBusy('')
      setBoard((prev) => ({
        ...prev,
        error: '',
        selected: (body && body.thread) || prev.selected,
        history: (body && body.history) || prev.history,
        threads: (prev.threads || []).map((thread) => (
          body && body.thread && thread.thread_id === body.thread.thread_id ? body.thread : thread
        )),
      }))
    }).catch((err) => {
      setBusy('')
      setBoard((prev) => ({
        ...prev,
        error: err && err.message ? err.message : 'The pane could not record that decision.',
      }))
    })
  }

  return jsxs('div', {
    style: { color: ink, font: '14px/1.4 "Iowan Old Style", Palatino, serif' },
    children: [
      jsxs('header', {
        style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
        children: [
          jsx('h1', { style: { fontSize: 18, margin: 0 }, children: 'Front door' }),
          jsx('span', { style: chipStyle('normal'), children: board.data_label || 'demo data' }),
        ],
      }),
      jsx('p', {
        style: { color: mute, margin: '8px 0' },
        children: `${(board.status && board.status.line) || 'Watching the inbox'} · ${age}s`,
      }),
      board.error ? jsx('p', { style: { color: '#991b1b' }, children: board.error }) : null,
      jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Inbox' }),
      threads.length
        ? jsx('ul', {
            style: { listStyle: 'none', padding: 0, margin: 0 },
            children: threads.map((thread) => jsxs('li', {
              onClick: () => setPicked(thread.thread_id),
              style: {
                padding: '8px 0',
                borderTop: `1px solid ${line}`,
                cursor: 'pointer',
                background: thread.thread_id === (board.focus || picked) ? '#fff' : 'transparent',
              },
              children: [
                jsx('span', { style: chipStyle(thread.label), children: thread.label }),
                jsx('div', { children: thread.from_name || thread.from_addr || 'Unknown sender' }),
                jsx('div', { style: { color: mute }, children: thread.subject }),
              ],
            }, thread.thread_id)),
          })
        : jsx('p', { style: { color: mute }, children: 'Queue is empty.' }),
      selected
        ? jsxs('section', {
            children: [
              jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Classification' }),
              classification
                ? jsxs('div', {
                    children: [
                      jsx('span', { style: chipStyle(classification.intent), children: classification.intent }),
                      jsx('span', { style: chipStyle(classification.urgency), children: classification.urgency }),
                      jsx('p', { children: classification.summary }),
                    ],
                  })
                : jsx('p', { style: { color: mute }, children: 'Not classified yet.' }),
              jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Draft' }),
              jsx('p', {
                style: { background: '#fff', border: `1px solid ${line}`, padding: 8, whiteSpace: 'pre-wrap' },
                children: selected.draft_body || 'No draft yet.',
              }),
              jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'Send gate' }),
              jsx('p', {
                children: selected.send_state === 'awaiting-approval'
                  ? 'Awaiting approval. Not sent.'
                  : selected.send_state === 'sent'
                    ? 'Sent after approval.'
                    : 'Not sent. Demo mode never sends.',
              }),
              jsx('p', { style: { color: mute }, children: selected.recipient ? `To ${selected.recipient}.` : 'No recipient yet.' }),
              jsxs('div', {
                style: { display: 'flex', gap: 8, margin: '8px 0' },
                children: [
                  jsx(Button, {
                    type: 'button',
                    variant: 'default',
                    disabled: !!busy,
                    onClick: () => decide('approve'),
                    children: busy === 'approve' ? 'Recording…' : 'Approve',
                  }),
                  jsx(Button, {
                    type: 'button',
                    variant: 'outline',
                    disabled: !!busy,
                    onClick: () => decide('deny'),
                    children: busy === 'deny' ? 'Recording…' : 'Deny',
                  }),
                ],
              }),
              jsx('h2', { style: { fontSize: 12, letterSpacing: '0.04em', textTransform: 'uppercase' }, children: 'History' }),
              (board.history || []).length
                ? jsx('ul', {
                    style: { listStyle: 'none', padding: 0, margin: 0 },
                    children: board.history.map((item) => jsxs('li', {
                      style: { padding: '6px 0', borderTop: `1px solid ${line}` },
                      children: [
                        jsx('div', { children: item.detail }),
                        jsx('div', { style: { color: mute }, children: item.at }),
                      ],
                    }, `${item.at}-${item.event}-${item.detail}`)),
                  })
                : jsx('p', { style: { color: mute }, children: 'No history yet.' }),
            ],
          })
        : null,
    ],
  })
}

export default {
  id: 'agentmail-frontdoor',
  name: 'AgentMail front door',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Front door',
      data: { placement: 'right', width: '320px' },
      render: () => jsx(FrontDoor, { rest: (path, options) => ctx.rest(path, options) }),
    })
  },
}
