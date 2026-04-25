<script lang="ts">
  import { onDestroy } from "svelte";
  import type { ReadinessReport } from "$lib/types";
  import { gateToColor, readinessToColor } from "$lib/types";
  import { ShieldAlert, Zap, Moon, X, AlertTriangle } from "lucide-svelte";

  interface Props {
    report: ReadinessReport;
    open?: boolean;
    onrest?: () => void;
    onpush?: () => void;
    ondismiss?: () => void;
  }

  let { report, open = false, onrest, onpush, ondismiss }: Props = $props();

  // ── Gate-derived display values ───────────────────────────────────────
  const GATE_TITLE: Record<string, string> = {
    REST_RECOMMENDED: "Your Body Needs Rest",
    MANDATORY_REST: "Rest Required Today",
    PROCEED_WITH_CAUTION: "Proceed With Care",
    PROCEED: "All Clear",
  };

  const GATE_ICON_COLOR: Record<string, string> = {
    PROCEED: "text-green-500",
    PROCEED_WITH_CAUTION: "text-yellow-500",
    REST_RECOMMENDED: "text-orange-500",
    MANDATORY_REST: "text-red-600",
  };

  const GATE_BORDER_COLOR: Record<string, string> = {
    PROCEED: "border-green-400",
    PROCEED_WITH_CAUTION: "border-yellow-400",
    REST_RECOMMENDED: "border-orange-400",
    MANDATORY_REST: "border-red-500",
  };

  const SCORE_CIRCLE_COLOR: Record<string, string> = {
    EXCELLENT: "bg-green-100 text-green-700 ring-green-300",
    GOOD: "bg-blue-100 text-blue-700 ring-blue-300",
    MODERATE: "bg-yellow-100 text-yellow-700 ring-yellow-300",
    POOR: "bg-orange-100 text-orange-700 ring-orange-300",
    VERY_POOR: "bg-red-100 text-red-700 ring-red-300",
  };

  const isMandatory = $derived(report.training_gate === "MANDATORY_REST");
  const gateTitle = $derived(
    GATE_TITLE[report.training_gate] ?? "Readiness Alert",
  );
  const iconColor = $derived(
    GATE_ICON_COLOR[report.training_gate] ?? "text-slate-500",
  );
  const borderColor = $derived(
    GATE_BORDER_COLOR[report.training_gate] ?? "border-slate-400",
  );
  const scoreClass = $derived(
    SCORE_CIRCLE_COLOR[report.readiness_label] ??
      "bg-slate-100 text-slate-700 ring-slate-300",
  );

  // ── Signal pills ──────────────────────────────────────────────────────
  function hrvPillClass(pct: number | null): string {
    if (pct == null) return "bg-slate-100 text-slate-500";
    if (pct >= -5) return "bg-green-100 text-green-700";
    if (pct >= -15) return "bg-yellow-100 text-yellow-700";
    return "bg-red-100 text-red-700";
  }

  function sleepPillClass(score: number | null): string {
    if (score == null) return "bg-slate-100 text-slate-500";
    if (score >= 75) return "bg-green-100 text-green-700";
    if (score >= 50) return "bg-yellow-100 text-yellow-700";
    return "bg-red-100 text-red-700";
  }

  function acwrPillClass(acwr: number | null): string {
    if (acwr == null) return "bg-slate-100 text-slate-500";
    if (acwr >= 1.5) return "bg-red-100 text-red-700";
    if (acwr >= 1.3) return "bg-yellow-100 text-yellow-700";
    return "bg-green-100 text-green-700";
  }

  // ── Body scroll lock ──────────────────────────────────────────────────
  $effect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
  });

  onDestroy(() => {
    document.body.style.overflow = "";
  });

  // ── Keyboard handler ──────────────────────────────────────────────────
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") ondismiss?.();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- Backdrop -->
  <!-- svelte-ignore a11y_interactive_supports_focus -->
  <div
    role="dialog"
    aria-modal="true"
    aria-label="Training override decision"
    tabindex="-1"
    class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4
           animate-backdrop"
    onclick={(e) => {
      if (e.target === e.currentTarget) ondismiss?.();
    }}
    onkeydown={(e) => {
      if (e.key === "Escape") ondismiss?.();
    }}
  >
    <!-- Panel -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5
             animate-panel max-h-[90vh] overflow-y-auto"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
      role="document"
    >
      <!-- Close button -->
      <button
        onclick={() => ondismiss?.()}
        class="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400
               hover:text-slate-600 hover:bg-slate-100 transition"
        aria-label="Close"
      >
        <X size={18} />
      </button>

      <!-- ── HEADER ─────────────────────────────────────────────────── -->
      <div class="flex flex-col items-center text-center gap-2 pt-1">
        <div class="p-3 rounded-full bg-slate-100 {iconColor}">
          {#if isMandatory}
            <ShieldAlert size={28} />
          {:else}
            <AlertTriangle size={28} />
          {/if}
        </div>
        <h2 class="text-xl font-bold text-slate-800">{gateTitle}</h2>
      </div>

      <!-- ── SCORE CIRCLE ───────────────────────────────────────────── -->
      <div class="flex flex-col items-center gap-1.5">
        <div
          class="w-20 h-20 rounded-full ring-4 flex items-center justify-center
                    {scoreClass}"
        >
          <span class="text-3xl font-bold tabular-nums leading-none">
            {report.readiness_score}
          </span>
        </div>
        <span
          class="text-xs font-semibold tracking-wide text-slate-500 uppercase"
        >
          {report.readiness_label.replace(/_/g, " ")}
        </span>
      </div>

      <!-- ── SIGNAL PILLS ───────────────────────────────────────────── -->
      <div class="flex justify-center gap-2 flex-wrap">
        <!-- HRV -->
        {#if report.key_signals?.hrv?.deviation_pct != null}
          {@const pct = report.key_signals.hrv.deviation_pct}
          <span
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium
                       {hrvPillClass(pct)}"
          >
            HRV {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
          </span>
        {:else}
          <span
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium bg-slate-100 text-slate-400"
          >
            HRV —
          </span>
        {/if}

        <!-- Sleep -->
        {#if report.key_signals?.sleep?.score != null}
          {@const score = report.key_signals.sleep.score}
          <span
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium
                       {sleepPillClass(score)}"
          >
            Sleep {score}/100
          </span>
        {:else}
          <span
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium bg-slate-100 text-slate-400"
          >
            Sleep —
          </span>
        {/if}

        <!-- ACWR -->
        {#if report.key_signals?.load?.acwr != null}
          {@const acwr = report.key_signals.load.acwr}
          <span
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium
                       {acwrPillClass(acwr)}"
          >
            ACWR {acwr.toFixed(2)}
          </span>
        {:else}
          <span
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium bg-slate-100 text-slate-400"
          >
            ACWR —
          </span>
        {/if}
      </div>

      <!-- ── NARRATIVE ──────────────────────────────────────────────── -->
      {#if report.narrative}
        <blockquote
          class="border-l-4 pl-4 italic text-sm text-slate-600 leading-relaxed
                           {borderColor}"
        >
          {report.narrative}
        </blockquote>
      {/if}

      <!-- ── RECOMMENDATIONS ────────────────────────────────────────── -->
      {#if report.recommendations?.length > 0}
        <div class="space-y-1.5">
          <p
            class="text-xs font-semibold text-slate-400 uppercase tracking-wide"
          >
            Coach says
          </p>
          <ul class="space-y-1">
            {#each report.recommendations.slice(0, 3) as rec}
              <li class="flex items-start gap-2 text-sm text-slate-600">
                <span
                  class="mt-1 w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0"
                ></span>
                {rec}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- ── FLAGS ──────────────────────────────────────────────────── -->
      {#if report.flags?.length > 0}
        <div class="flex flex-wrap gap-1.5">
          {#each report.flags as flag}
            <span
              class="inline-flex items-center gap-1 bg-red-50 border border-red-100
                         text-red-600 text-xs font-medium rounded-full px-2.5 py-1"
            >
              ⚑ {flag}
            </span>
          {/each}
        </div>
      {/if}

      <!-- ── DECISION BUTTONS ───────────────────────────────────────── -->
      <div class="space-y-3 pt-1">
        <!-- REST button -->
        <button
          onclick={() => onrest?.()}
          class="w-full bg-green-600 hover:bg-green-700 active:scale-[0.99] text-white
                 rounded-xl py-4 px-5 flex items-center gap-4 transition-all duration-150 shadow-sm"
        >
          <Moon size={22} class="shrink-0" />
          <div class="text-left">
            <p class="font-semibold text-base leading-tight">
              Rest as Recommended
            </p>
            <p class="text-green-100 text-xs mt-0.5 leading-snug">
              Listen to your body. Come back stronger tomorrow.
            </p>
          </div>
        </button>

        <!-- PUSH button -->
        <div class="relative group">
          <button
            onclick={() => !isMandatory && onpush?.()}
            disabled={isMandatory}
            class="w-full bg-white border-2 rounded-xl py-4 px-5 flex items-center gap-4
                   transition-all duration-150
                   {isMandatory
              ? 'border-slate-200 text-slate-300 cursor-not-allowed'
              : 'border-slate-300 text-slate-700 hover:border-slate-400 hover:shadow-sm active:scale-[0.99]'}"
          >
            <Zap
              size={22}
              class="shrink-0 {isMandatory
                ? 'text-slate-300'
                : 'text-slate-500'}"
            />
            <div class="text-left">
              <p class="font-semibold text-base leading-tight">Push Through</p>
              <p
                class="text-xs mt-0.5 leading-snug
                        {isMandatory ? 'text-slate-300' : 'text-slate-400'}"
              >
                {#if isMandatory}
                  Mandatory rest — pushing through is not recommended
                {:else}
                  Volume reduced 25%, intensity capped at Z3
                {/if}
              </p>
            </div>
          </button>

          <!-- Tooltip for mandatory rest -->
          {#if isMandatory}
            <div
              class="absolute -top-9 left-1/2 -translate-x-1/2 bg-slate-800 text-white
                        text-xs rounded-lg px-3 py-1.5 whitespace-nowrap shadow-lg
                        opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10
                        after:content-[''] after:absolute after:top-full after:left-1/2
                        after:-translate-x-1/2 after:border-4 after:border-transparent
                        after:border-t-slate-800"
            >
              Mandatory rest — this cannot be overridden
            </div>
          {/if}
        </div>
      </div>

      <!-- ── FOOTER ─────────────────────────────────────────────────── -->
      <p class="text-center text-xs text-slate-400 pt-1">
        This decision will update your training plan for today.
      </p>
    </div>
  </div>
{/if}

<style>
  @keyframes backdrop-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes panel-in {
    from {
      opacity: 0;
      transform: scale(0.95) translateY(8px);
    }
    to {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }
  .animate-backdrop {
    animation: backdrop-in 200ms ease-out both;
  }
  .animate-panel {
    animation: panel-in 200ms ease-out both;
  }
</style>
