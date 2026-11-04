export function useState(initial) {
  const value = typeof initial === "function" ? initial() : initial
  return [value, () => {}]
}

export function useEffect(effect) {
  const cleanup = effect()
  if (typeof cleanup === "function") cleanup()
}
