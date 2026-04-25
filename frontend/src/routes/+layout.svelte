<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import {
    userId,
    todayReport,
    currentPlan,
    globalError,
    isLoading,
    pipelineRunning,
    overridePrompt,
  } from "$lib/stores";
  import {
    getCurrentPlan,
    getReadinessReport,
    getOverridePrompt,
    getStoredUserId,
    storeUserId,
    runFullPipeline,
  } from "$lib/api";
  import { gateToColor, todayStr } from "$lib/types";

  let { children } = $props();
  const devId = import.meta.env.VITE_DEV_USER_ID;
  if (devId) storeUserId(devId);
  // ── Route → page title map ──────────────────────────────────────────
  const ROUTE_TITLES: Record<string, string> = {
    "/": "Dashboard",
    "/checkin": "Daily Check-in",
    "/stats": "Statistics",
    "/settings": "Settings",
  };
  let pageTitle = $derived(ROUTE_TITLES[$page.url.pathname] ?? "FitCoach AI");

  // ── Error auto-dismiss ──────────────────────────────────────────────
  let errorTimer: ReturnType<typeof setTimeout>;
  $effect(() => {
    if ($globalError) {
      clearTimeout(errorTimer);
      errorTimer = setTimeout(() => globalError.set(null), 5000);
    }
  });

  // ── Gate color → Tailwind class ─────────────────────────────────────
  const gateClasses: Record<string, string> = {
    green: "bg-green-500",
    yellow: "bg-yellow-400",
    orange: "bg-orange-500",
    red: "bg-red-500",
  };
  let gateBg = $derived(
    $todayReport
      ? (gateClasses[gateToColor($todayReport.training_gate)] ?? "bg-slate-400")
      : "bg-slate-400",
  );

  // ── Nav links ───────────────────────────────────────────────────────
  const NAV = [
    { href: "/", label: "Dashboard", icon: "🏠" },
    { href: "/checkin", label: "Check-in", icon: "✅" },
    // { href: "/stats", label: "Stats", icon: "📊" },
    { href: "/settings", label: "Settings", icon: "⚙️" },
  ];

  // ── Pipeline run ────────────────────────────────────────────────────
  async function handleRunPipeline() {
    if (!$userId || $pipelineRunning) return;
    pipelineRunning.set(true);
    globalError.set(null);
    try {
      const result = await runFullPipeline($userId);
      if (!result.success) {
        globalError.set(result.error ?? "Pipeline failed");
        return;
      }
      const [planRes, reportRes] = await Promise.allSettled([
        getCurrentPlan($userId),
        getReadinessReport($userId),
      ]);
      if (planRes.status === "fulfilled") currentPlan.set(planRes.value);
      if (reportRes.status === "fulfilled") todayReport.set(reportRes.value);
    } catch (e: unknown) {
      globalError.set(e instanceof Error ? e.message : "Pipeline failed");
    } finally {
      pipelineRunning.set(false);
    }
  }

  // ── Bootstrap on mount ──────────────────────────────────────────────
  onMount(async () => {
    let uid = getStoredUserId();
    if (!uid) {
      uid = import.meta.env.VITE_DEV_USER_ID ?? null;
      if (uid) storeUserId(uid);
    }
    if (!uid) return;
    userId.set(uid);

    isLoading.set(true);
    try {
      const [planRes, reportRes, overrideRes] = await Promise.allSettled([
        getCurrentPlan(uid),
        getReadinessReport(uid),
        getOverridePrompt(uid),
      ]);
      if (planRes.status === "fulfilled") currentPlan.set(planRes.value);
      if (reportRes.status === "fulfilled") todayReport.set(reportRes.value);
      if (overrideRes.status === "fulfilled")
        overridePrompt.set(overrideRes.value);
    } finally {
      isLoading.set(false);
    }
  });
</script>

<svelte:head>
  <title>{pageTitle} — FitCoach AI</title>
</svelte:head>

<!-- ── Loading progress bar ───────────────────────────────────────────── -->
{#if $isLoading || $pipelineRunning}
  <div
    class="fixed top-0 left-0 right-0 z-50 h-0.5 bg-blue-100 overflow-hidden"
  >
    <div class="h-full bg-blue-500 animate-pulse w-2/3"></div>
  </div>
{/if}

<!-- ── Global error toast ─────────────────────────────────────────────── -->
{#if $globalError}
  <div
    class="fixed z-50 top-4 right-4 lg:top-auto lg:bottom-6 lg:right-6
              max-w-sm bg-red-600 text-white rounded-xl shadow-lg px-4 py-3
              flex items-start gap-3 text-sm"
  >
    <span class="flex-1">{$globalError}</span>
    <button
      onclick={() => globalError.set(null)}
      class="text-white/80 hover:text-white transition text-base leading-none mt-0.5"
      aria-label="Dismiss">✕</button
    >
  </div>
{/if}

<!-- ── Root layout ────────────────────────────────────────────────────── -->
<div class="min-h-screen flex">
  <!-- ── Desktop sidebar (lg+) ──────────────────────────────────────── -->
  <aside
    class="hidden lg:flex flex-col fixed left-0 top-0 bottom-0 w-64
                bg-slate-900 border-r border-slate-700/60 text-white z-40"
  >
    <!-- Logo -->
    <div class="px-6 py-5 border-b border-white/10 flex items-center gap-2">
      <span class="text-yellow-400 text-xl">⚡</span>
      <span class="font-display font-bold text-lg tracking-tight"
        >FitCoach AI</span
      >
    </div>

    <!-- Nav links -->
    <nav class="flex-1 px-3 py-4 space-y-1">
      {#each NAV as link}
        {@const active = $page.url.pathname === link.href}
        <a
          href={link.href}
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                 transition-all duration-150
                 {active
            ? 'bg-blue-600/20 text-white border-l-2 border-blue-400 pl-[10px]'
            : 'text-slate-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent pl-[10px]'}"
        >
          <span class="text-base w-5 text-center">{link.icon}</span>
          {link.label}
        </a>
      {/each}
    </nav>

    <!-- Readiness pill -->
    <div class="px-5 py-4 border-t border-white/10">
      {#if $todayReport}
        <div class="flex items-center gap-3">
          <div class="w-2.5 h-2.5 rounded-full flex-shrink-0 {gateBg}"></div>
          <div class="min-w-0">
            <p class="text-xs text-slate-400 leading-tight">
              Today's Readiness
            </p>
            <p class="text-white font-semibold text-sm leading-tight truncate">
              {$todayReport.readiness_score}/100
              <span class="font-normal text-slate-400"
                >· {$todayReport.training_gate.replace(/_/g, " ")}</span
              >
            </p>
          </div>
        </div>
      {:else}
        <p class="text-xs text-slate-500">No readiness data yet</p>
      {/if}
    </div>
  </aside>

  <!-- ── Main content area ──────────────────────────────────────────── -->
  <div class="flex-1 flex flex-col lg:ml-64 min-h-screen">
    <!-- Top bar -->
    <header
      class="hidden lg:flex items-center justify-between
                   px-6 py-4 bg-slate-900 border-b border-slate-700/60 sticky top-0 z-30"
    >
      <h1 class="text-lg font-semibold text-slate-100">{pageTitle}</h1>
      <button
        onclick={handleRunPipeline}
        disabled={$pipelineRunning}
        class="btn-primary flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {#if $pipelineRunning}
          <span
            class="inline-block w-3.5 h-3.5 border-2 border-white/40 border-t-white
                       rounded-full animate-spin"
          ></span>
          Running…
        {:else}
          <span>⚡</span> Run Pipeline
        {/if}
      </button>
    </header>

    <!-- Page content -->
    <main class="flex-1 overflow-y-auto pb-20 lg:pb-0">
      {@render children()}
    </main>
  </div>

  <!-- ── Mobile bottom tab bar ──────────────────────────────────────── -->
  <nav
    class="lg:hidden fixed bottom-0 left-0 right-0 z-40
              bg-slate-900 border-t border-slate-700/60 shadow-lg
              flex items-stretch"
  >
    {#each NAV as tab}
      {@const active = $page.url.pathname === tab.href}
      <a
        href={tab.href}
        class="flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs font-medium
               transition-colors
               {active
          ? 'text-blue-500'
          : 'text-slate-400 hover:text-slate-600'}"
      >
        <span class="text-lg leading-tight">{tab.icon}</span>
        <span class="leading-tight">{tab.label}</span>
      </a>
    {/each}
  </nav>
</div>
