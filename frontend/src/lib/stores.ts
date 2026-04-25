import { writable, derived } from 'svelte/store'
import type { TrainingPlan, ReadinessReport, OverridePrompt, UserProfile } from './types'
import { getStoredUserId } from './api'

// ── Writable stores ───────────────────────────────────────────────────────

export const userId = writable<string | null>(getStoredUserId())

export const currentPlan = writable<TrainingPlan | null>(null)

export const todayReport = writable<ReadinessReport | null>(null)

export const overridePrompt = writable<OverridePrompt | null>(null)

export const userProfile = writable<UserProfile | null>(null)

export const isLoading = writable<boolean>(false)

export const pipelineRunning = writable<boolean>(false)

export const globalError = writable<string | null>(null)

export const showOverrideModal = writable<boolean>(false)

// ── Derived stores ────────────────────────────────────────────────────────

export const todaySession = derived(currentPlan, ($plan) => {
  if (!$plan) return null
  const today = new Date().toISOString().split('T')[0]
  return $plan.sessions.find(s => s.date === today) ?? null
})

export const tomorrowSession = derived(currentPlan, ($plan) => {
  if (!$plan) return null
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0]
  return $plan.sessions.find(s => s.date === tomorrow) ?? null
})

export const weekSessions = derived(currentPlan, ($plan) => {
  if (!$plan) return []
  const today = new Date()
  const monday = new Date(today)
  monday.setDate(today.getDate() - today.getDay() + 1)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  const mondayStr = monday.toISOString().split('T')[0]
  const sundayStr = sunday.toISOString().split('T')[0]
  return $plan.sessions.filter(s => s.date >= mondayStr && s.date <= sundayStr)
})

// ── Reset helper ──────────────────────────────────────────────────────────

export function clearAllStores(): void {
  currentPlan.set(null)
  todayReport.set(null)
  overridePrompt.set(null)
  userProfile.set(null)
  isLoading.set(false)
  pipelineRunning.set(false)
  globalError.set(null)
  showOverrideModal.set(false)
}
