import { useEffect, useState } from 'react'

type Listener = () => void

const listeners = new Set<Listener>()
let intervalId: ReturnType<typeof setInterval> | null = null

function attach() {
  if (intervalId !== null) return
  intervalId = setInterval(() => {
    listeners.forEach((l) => l())
  }, 1000)
}

function detach() {
  if (listeners.size > 0 || intervalId === null) return
  clearInterval(intervalId)
  intervalId = null
}

export function useNowTick(): number {
  const [, force] = useState(0)

  useEffect(() => {
    const listener = () => force((n) => n + 1)
    listeners.add(listener)
    attach()
    return () => {
      listeners.delete(listener)
      detach()
    }
  }, [])

  return Date.now()
}

export function useIsFirstTick(): boolean {
  const now = useNowTick()
  return now > 0
}
