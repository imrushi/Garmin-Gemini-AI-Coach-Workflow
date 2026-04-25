<script lang="ts">
  import type { TrainingSession, IntensityZone } from "$lib/types";
  import { sportToEmoji, formatDuration, formatDistance } from "$lib/types";
  import {
    ChevronDown,
    ChevronUp,
    Droplets,
    Zap,
    Clock,
    Target,
  } from "lucide-svelte";

  interface Props {
    session: TrainingSession;
    isToday?: boolean;
    isPast?: boolean;
    expanded?: boolean;
    compact?: boolean;
    ontoggle?: () => void;
  }

  let {
    session,
    isToday = false,
    isPast = false,
    expanded = false,
    compact = false,
    ontoggle,
  }: Props = $props();

  // ── Zone colours ──────────────────────────────────────────────────────
  const ZONE_CLASS: Record<IntensityZone, string> = {
    Z1: "bg-slate-100 text-slate-700",
    Z2: "bg-green-100 text-green-700",
    Z3: "bg-yellow-100 text-yellow-700",
    Z4: "bg-orange-100 text-orange-700",
    Z5: "bg-red-100 text-red-700",
  };

  function zoneClass(z: IntensityZone | null): string {
    return z
      ? (ZONE_CLASS[z] ?? "bg-slate-100 text-slate-600")
      : "bg-slate-100 text-slate-600";
  }

  const isRest = $derived(session.sport === "rest");

  // ── Date helpers ──────────────────────────────────────────────────────
  /** e.g. "Mon 28" */
  function fmtShort(dateStr: string): { day: string; num: string } {
    const d = new Date(dateStr + "T00:00:00");
    return {
      day: d.toLocaleDateString("en-GB", { weekday: "short" }),
      num: d.toLocaleDateString("en-GB", { day: "numeric" }),
    };
  }

  /** e.g. "Monday 28 April" */
  function fmtLong(dateStr: string): string {
    return new Date(dateStr + "T00:00:00").toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  }

  let dateShort = $derived(fmtShort(session.date));
  let dateLong = $derived(fmtLong(session.date));

  const hasNutrition = $derived(
    !!(
      session.nutrition?.pre_session ||
      session.nutrition?.during_session ||
      session.nutrition?.post_session ||
      session.nutrition?.daily_notes
    ),
  );

  const nutritionSlots = $derived([
    { label: "Pre-session", value: session.nutrition?.pre_session ?? null },
    { label: "During", value: session.nutrition?.during_session ?? null },
    { label: "Post-session", value: session.nutrition?.post_session ?? null },
  ]);
</script>

<!-- ══════════════════════════════════════════════════════════════════════ -->
<!--  COMPACT MODE                                                          -->
<!-- ══════════════════════════════════════════════════════════════════════ -->
{#if compact}
  <div class="session-card-compact-wrapper">
    <!-- Card -->
    <div
      role="button"
      tabindex="0"
      onclick={() => ontoggle?.()}
      onkeydown={(e) => e.key === "Enter" && ontoggle?.()}
      class="rounded-lg border p-3 cursor-pointer transition hover:shadow-md select-none
             {isToday
        ? 'border-blue-500 border-2 bg-blue-50'
        : isRest
          ? 'border-slate-200 bg-slate-50'
          : 'border-slate-200 bg-white'}
             {isPast ? 'opacity-70' : ''}"
    >
      <!-- Row 1: emoji + day + date number -->
      <div class="flex items-center justify-between mb-1.5">
        <div class="flex items-center gap-1.5">
          <span
            class="text-xl leading-none"
            role="img"
            aria-label={session.sport}
          >
            {sportToEmoji(session.sport)}
          </span>
          <span class="text-xs text-slate-400 font-medium">{dateShort.day}</span
          >
        </div>
        <span class="text-xs text-slate-400">{dateShort.num}</span>
      </div>

      {#if isRest}
        <p class="text-xs text-slate-400 font-medium">Rest day</p>
      {:else}
        <!-- Row 2: title -->
        <p
          class="text-sm font-medium text-slate-800 truncate leading-snug mb-1.5"
        >
          {session.title}
        </p>

        <!-- Row 3: duration + zone -->
        <div class="flex items-center gap-1.5 flex-wrap">
          {#if session.duration_min}
            <span
              class="inline-flex items-center gap-0.5 text-xs bg-slate-100 text-slate-600 rounded px-1.5 py-0.5"
            >
              <Clock size={10} />{formatDuration(session.duration_min)}
            </span>
          {/if}
          {#if session.intensity_zone}
            <span
              class="inline-flex items-center text-xs rounded px-1.5 py-0.5 font-medium
                         {zoneClass(session.intensity_zone)}"
            >
              {session.intensity_zone}
            </span>
          {/if}
        </div>
      {/if}

      <!-- Expand chevron -->
      {#if !isRest}
        <div class="flex justify-end mt-1">
          {#if expanded}
            <ChevronUp size={13} class="text-slate-300" />
          {:else}
            <ChevronDown size={13} class="text-slate-300" />
          {/if}
        </div>
      {/if}
    </div>

    <!-- Inline expansion panel -->
    {#if !isRest}
      <div
        class="expansion-panel overflow-hidden transition-all duration-300 ease-in-out
               {expanded ? 'max-h-96 opacity-100 mt-1' : 'max-h-0 opacity-0'}"
      >
        <div class="card p-4 text-sm space-y-2.5 rounded-t-none">
          <!-- Key focus -->
          <p
            class="italic text-slate-500 border-l-4 border-blue-400 pl-3 text-xs leading-snug"
          >
            {session.key_focus}
          </p>

          <!-- Description -->
          <p class="text-slate-600 leading-relaxed text-xs">
            {session.description}
          </p>

          <!-- Nutrition summary (daily_notes only in compact expansion) -->
          {#if hasNutrition}
            <div class="pt-2 border-t border-slate-100 flex items-start gap-2">
              <Droplets size={13} class="text-blue-400 mt-0.5 shrink-0" />
              <div class="text-xs text-slate-500 space-y-0.5">
                {#each nutritionSlots as slot}
                  {#if slot.value}
                    <p>
                      <span class="font-medium text-slate-700"
                        >{slot.label}:</span
                      >
                      {slot.value}
                    </p>
                  {/if}
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- ══════════════════════════════════════════════════════════════════════ -->
  <!--  FULL / HERO MODE                                                       -->
  <!-- ══════════════════════════════════════════════════════════════════════ -->
{:else}
  <div
    class="rounded-xl border p-6 shadow-sm bg-white
           {isToday ? 'ring-2 ring-blue-500' : 'border-slate-200'}"
  >
    <!-- Sport + date -->
    <div class="flex items-start gap-4">
      <span
        class="text-4xl leading-none shrink-0 mt-1"
        role="img"
        aria-label={session.sport}
      >
        {sportToEmoji(session.sport)}
      </span>
      <div>
        <p class="text-lg text-slate-400 capitalize leading-tight">
          {session.sport.replace(/_/g, " ")}
        </p>
        <p class="text-xs text-slate-400">{dateLong}</p>
      </div>
    </div>

    <!-- Title -->
    <h2 class="text-2xl font-bold text-slate-800 mt-3 leading-snug">
      {session.title}
    </h2>

    <!-- Key focus -->
    <p
      class="italic text-slate-500 mt-2 border-l-4 border-blue-500 pl-3 text-sm leading-relaxed"
    >
      {session.key_focus}
    </p>

    <!-- Details row -->
    <div class="flex flex-wrap gap-3 mt-4">
      {#if session.duration_min}
        <div class="flex items-center gap-1.5 text-sm text-slate-600">
          <Clock size={15} class="text-slate-400" />
          <span>{formatDuration(session.duration_min)}</span>
        </div>
      {/if}

      {#if session.intensity_zone}
        <div class="flex items-center gap-1.5">
          <Zap size={15} class="text-slate-400" />
          <span class="badge text-xs {zoneClass(session.intensity_zone)}">
            {session.intensity_zone}
          </span>
        </div>
      {/if}

      {#if session.distance_m}
        <div class="flex items-center gap-1.5 text-sm text-slate-600">
          <Target size={15} class="text-slate-400" />
          <span>{formatDistance(session.distance_m)}</span>
        </div>
      {/if}
    </div>

    <!-- Description -->
    <p class="text-sm text-slate-600 leading-relaxed mt-4">
      {session.description}
    </p>

    <!-- Strength exercises -->
    {#if session.exercises?.length}
      <div class="mt-5">
        <p
          class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2"
        >
          Exercises
        </p>
        <div class="space-y-1.5">
          {#each session.exercises as ex}
            <div class="flex items-baseline gap-2 text-sm">
              <span class="font-medium text-slate-700 min-w-0"
                >{ex.exercise}</span
              >
              <span class="text-slate-400 shrink-0"
                >{ex.sets}×{ex.reps_or_duration}</span
              >
              {#if ex.notes}
                <span class="text-slate-400 text-xs truncate">— {ex.notes}</span
                >
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Nutrition section -->
    {#if hasNutrition}
      <div class="mt-5 pt-4 border-t border-slate-100">
        <p
          class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3"
        >
          🍽 Nutrition
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {#each nutritionSlots as slot}
            {#if slot.value}
              <div class="bg-slate-50 rounded-lg p-3">
                <p class="text-xs font-semibold text-slate-500 mb-1">
                  {slot.label}
                </p>
                <p class="text-xs text-slate-600 leading-relaxed">
                  {slot.value}
                </p>
              </div>
            {/if}
          {/each}
        </div>
        {#if session.nutrition?.daily_notes}
          <p class="text-xs text-slate-500 mt-2 italic">
            {session.nutrition.daily_notes}
          </p>
        {/if}
      </div>
    {/if}

    <!-- Warnings -->
    {#if session.override_applied || session.readiness_adjusted}
      <div class="mt-4 space-y-1.5">
        {#if session.override_applied}
          <div
            class="flex items-center gap-2 text-xs text-amber-700 bg-amber-50
                      border border-amber-200 rounded-lg px-3 py-2"
          >
            <Zap size={12} class="shrink-0" />
            <span
              >Push-through override applied — session modified from rest
              recommendation.</span
            >
          </div>
        {/if}
        {#if session.readiness_adjusted}
          <div
            class="flex items-center gap-2 text-xs text-blue-700 bg-blue-50
                      border border-blue-200 rounded-lg px-3 py-2"
          >
            <Target size={12} class="shrink-0" />
            <span>Adjusted for today's readiness score.</span>
          </div>
        {/if}
      </div>
    {/if}
  </div>
{/if}
