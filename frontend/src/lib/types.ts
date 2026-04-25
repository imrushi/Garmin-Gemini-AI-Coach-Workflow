export interface HRVSignal {
  current_ms: number | null
  baseline_ms: number | null
  deviation_pct: number | null
  trend_3d: string | null
}

export interface SleepSignal {
  score: number | null
  duration_min: number | null
  deep_min: number | null
  rem_min: number | null
  quality_label: string | null
}

export interface LoadSignal {
  acwr: number | null
  acute_load: number | null
  chronic_load: number | null
  acwr_risk: string | null
}

export interface KeySignals {
  hrv: HRVSignal
  sleep: SleepSignal
  load: LoadSignal
  body_battery_morning: number | null
  resting_hr: number | null
  resting_hr_trend: string | null
  stress_avg: number | null
}

export interface ReadinessReport {
  report_date: string
  readiness_score: number
  readiness_label: 'EXCELLENT' | 'GOOD' | 'MODERATE' | 'POOR' | 'VERY_POOR'
  training_gate: 'PROCEED' | 'PROCEED_WITH_CAUTION' | 'REST_RECOMMENDED' | 'MANDATORY_REST'
  key_signals: KeySignals
  flags: string[]
  narrative: string
  recommendations: string[]
  data_completeness_pct: number
}

export interface NutritionGuidance {
  pre_session: string | null
  during_session: string | null
  post_session: string | null
  daily_notes: string | null
}

export type SportType = 'swim' | 'bike' | 'run' | 'brick' | 'strength' |
                        'yoga' | 'active_recovery' | 'rest'

export type IntensityZone = 'Z1' | 'Z2' | 'Z3' | 'Z4' | 'Z5'

export interface StrengthExercise {
  exercise: string
  sets: number
  reps_or_duration: string
  notes: string | null
}

export interface TrainingSession {
  date: string
  day_of_week: string
  sport: SportType
  status: 'planned' | 'completed' | 'skipped' | 'modified'
  duration_min: number | null
  distance_m: number | null
  intensity_zone: IntensityZone | null
  title: string
  description: string
  key_focus: string
  exercises: StrengthExercise[]
  nutrition: NutritionGuidance
  override_applied: string | null
  readiness_adjusted: boolean
}

export interface WeeklyTargets {
  week_number: number
  week_start: string
  total_volume_min: number
  long_session_sport: SportType | null
  key_workout: string | null
  weekly_theme: string | null
  intensity_distribution: Record<string, number>
}

export interface TrainingPlan {
  plan_id: string
  user_id: string
  generated_at: string
  valid_from: string
  valid_to: string
  goal_event: string | null
  goal_date: string | null
  weeks_to_goal: number | null
  sessions: TrainingSession[]
  weekly_targets: WeeklyTargets[]
  readiness_score_at_generation: number | null
  training_gate_at_generation: string | null
  override_applied: string | null
  plan_rationale: string
  nutrition_weekly_notes: string | null
}

export interface CheckInRequest {
  user_id: string
  check_in_date: string
  perceived_effort: number | null
  mood: number | null
  free_text: string | null
  override_choice: 'rest_as_recommended' | 'push_through' | null
  override_reason: string | null
}

export interface CheckInResponse {
  saved: boolean
  override_applied: string | null
  plan_updated: boolean
  message: string
}

export interface OverridePrompt {
  show_prompt: boolean
  training_gate: string
  readiness_score: number | null
  narrative: string | null
  already_decided: boolean
  decision: string | null
}

export interface UserProfile {
  user_id: string
  display_name: string | null
  goal_event: string | null
  goal_date: string | null
  fitness_level: string | null
  medical_conditions: string[]
  dietary_preference: string | null
  max_weekly_hours: number | null
  swim_equipment: string | null
  swim_strokes: string | null
  model_analysis: string
  model_planning: string
}

// ── Helper types & functions ──────────────────────────────────────────────

export type GateColor = 'green' | 'yellow' | 'orange' | 'red'

export function gateToColor(gate: string): GateColor {
  const map: Record<string, GateColor> = {
    'PROCEED': 'green',
    'PROCEED_WITH_CAUTION': 'yellow',
    'REST_RECOMMENDED': 'orange',
    'MANDATORY_REST': 'red',
  }
  return map[gate] ?? 'green'
}

export function readinessToColor(score: number): string {
  if (score >= 85) return 'text-green-600'
  if (score >= 70) return 'text-blue-600'
  if (score >= 50) return 'text-yellow-600'
  if (score >= 30) return 'text-orange-600'
  return 'text-red-600'
}

export function sportToEmoji(sport: SportType): string {
  const map: Record<SportType, string> = {
    swim: '🏊', bike: '🚴', run: '🏃', brick: '🚴🏃',
    strength: '💪', yoga: '🧘', active_recovery: '🚶', rest: '😴',
  }
  return map[sport] ?? '🏋️'
}

export function formatDuration(min: number | null): string {
  if (!min) return '—'
  if (min < 60) return `${min}min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m === 0 ? `${h}h` : `${h}h ${m}min`
}

export function formatDistance(m: number | null): string {
  if (!m) return ''
  if (m >= 1000) return `${(m / 1000).toFixed(1)}km`
  return `${Math.round(m)}m`
}

export function todayStr(): string {
  return new Date().toISOString().split('T')[0]
}
