import { pathToFileURL } from "node:url"

const target = process.argv[2]
if (!target) {
  console.error("usage: check-desktop.mjs <plugin.js>")
  process.exit(2)
}

const mod = await import(pathToFileURL(target).href)
const calls = []
const ctx = {
  register(contribution) {
    calls.push(contribution)
  },
  rest: async () => {
    throw new Error("Gateway route unavailable")
  },
}

if (!mod.default || typeof mod.default.register !== "function") {
  console.error("plugin.js has no register")
  process.exit(1)
}
mod.default.register(ctx)
if (calls.length !== 1 || calls[0].area !== "panes") {
  console.error("expected one panes contribution")
  process.exit(1)
}
const vnode = calls[0].render()
if (!vnode || !vnode.props) {
  console.error("render returned nothing")
  process.exit(1)
}
console.log(JSON.stringify({ id: mod.default.id, area: calls[0].area, title: calls[0].title }))
