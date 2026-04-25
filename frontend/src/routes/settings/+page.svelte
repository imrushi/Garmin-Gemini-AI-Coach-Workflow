<script lang="ts">
  import { onMount } from "svelte";
  import { userId, userProfile, globalError } from "$lib/stores";
  import { getProfile, updateProfile } from "$lib/api";
  import {
    Settings,
    User,
    Cpu,
    RefreshCw,
    Info,
    ChevronDown,
    ChevronUp,
    CheckCircle,
  } from "lucide-svelte";

  // ── State ─────────────────────────────────────────────────────────────
  let loading = $state(true);
  let savingModels = $state(false);
  let syncLoading = $state(false);

  /** toast: null | { message, kind } */
  let toast = $state<{ message: string; kind: "success" | "error" } | null>(
    null,
  );
  let toastTimer: ReturnType<typeof setTimeout> | null = null;

  function showToast(message: string, kind: "success" | "error" = "success") {
    toast = { message, kind };
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast = null;
    }, 3500);
  }

  // ── Accordion ─────────────────────────────────────────────────────────
  let openSection = $state<string | null>(null);
  function toggle(id: string) {
    openSection = openSection === id ? null : id;
  }

  // ── Model config form ─────────────────────────────────────────────────
  let modelAnalysis = $state("");
  let modelPlanning = $state("");

  // ── Profile edit stub ─────────────────────────────────────────────────
  let editingProfile = $state(false);

  const MODEL_OPTIONS = [
    {
      group: "OpenRouter — Anthropic",
      options: [
        {
          value: "openrouter/anthropic/claude-3-5-sonnet-20241022",
          label: "Claude 3.5 Sonnet",
        },
        {
          value: "openrouter/anthropic/claude-sonnet-4-6",
          label: "Claude Sonnet 4.6",
        },
      ],
    },
    {
      group: "OpenRouter — Google",
      options: [
        {
          value: "openrouter/google/gemini-flash-1.5",
          label: "Gemini Flash 1.5",
        },
      ],
    },
    {
      group: "OpenRouter — Meta",
      options: [
        {
          value: "openrouter/meta-llama/llama-3.1-70b-instruct",
          label: "Llama 3.1 70B",
        },
      ],
    },
    {
      group: "Local (Ollama)",
      options: [
        { value: "ollama/llama3.2:3b", label: "Llama 3.2 3B" },
        { value: "ollama/llama3.3:70b", label: "Llama 3.3 70B" },
      ],
    },
  ];

  // ── Load profile ──────────────────────────────────────────────────────
  onMount(async () => {
    const uid = $userId;
    if (!uid) {
      loading = false;
      return;
    }
    try {
      const profile = await getProfile(uid);
      userProfile.set(profile);
      modelAnalysis = profile.model_analysis ?? "";
      modelPlanning = profile.model_planning ?? "";
    } catch (e: unknown) {
      globalError.set(
        e instanceof Error ? e.message : "Failed to load profile",
      );
    } finally {
      loading = false;
    }
  });

  // ── Save model config ─────────────────────────────────────────────────
  async function saveModelConfig() {
    const uid = $userId;
    if (!uid) return;
    savingModels = true;
    try {
      const updated = await updateProfile(uid, {
        model_analysis: modelAnalysis,
        model_planning: modelPlanning,
      });
      userProfile.set(updated);
      showToast("Model configuration saved");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Save failed", "error");
    } finally {
      savingModels = false;
    }
  }

  // ── Sync Garmin ───────────────────────────────────────────────────────
  async function triggerSync() {
    syncLoading = true;
    try {
      // Endpoint not yet implemented — show coming-soon toast
      showToast(
        "Garmin sync coming soon — endpoint not yet available",
        "error",
      );
    } finally {
      syncLoading = false;
    }
  }

  const APP_VERSION = "0.1.0-alpha";
</script>

<!-- Toast -->
{#if toast}
  <div
    class="fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-sm font-medium
           {toast.kind === 'success'
      ? 'bg-green-600 text-white'
      : 'bg-red-600 text-white'}
           animate-slide-in"
    role="alert"
  >
    {#if toast.kind === "success"}
      <CheckCircle size={15} class="shrink-0" />
    {/if}
    {toast.message}
  </div>
{/if}

<div class="max-w-2xl mx-auto py-8 px-4 space-y-6 animate-fade-in">
  <!-- Header -->
  <div class="flex items-center gap-2">
    <Settings size={22} class="text-blue-500" />
    <h1 class="text-2xl font-bold text-slate-100">Settings</h1>
  </div>

  <!-- ── SECTION 1: Athlete Profile ────────────────────────────────── -->
  <div class="card overflow-hidden">
    <button
      onclick={() => toggle("profile")}
      class="w-full flex items-center justify-between p-5 text-left hover:bg-slate-700/50 transition"
    >
      <div class="flex items-center gap-3">
        <User size={18} class="text-slate-400 shrink-0" />
        <span class="font-semibold text-slate-100">Athlete Profile</span>
      </div>
      {#if openSection === "profile"}
        <ChevronUp size={16} class="text-slate-400" />
      {:else}
        <ChevronDown size={16} class="text-slate-400" />
      {/if}
    </button>

    {#if openSection === "profile"}
      <div class="px-5 pb-5 border-t border-slate-700 space-y-4 pt-4">
        {#if loading}
          <!-- Skeleton -->
          <div class="space-y-3">
            {#each [1, 2, 3, 4] as _}
              <div class="h-5 bg-slate-700 rounded animate-pulse w-3/4"></div>
            {/each}
          </div>
        {:else if $userProfile}
          <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt
                class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5"
              >
                Name
              </dt>
              <dd class="text-slate-200">{$userProfile.display_name ?? "—"}</dd>
            </div>
            <div>
              <dt
                class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5"
              >
                Fitness Level
              </dt>
              <dd class="text-slate-200 capitalize">
                {$userProfile.fitness_level ?? "—"}
              </dd>
            </div>
            <div>
              <dt
                class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5"
              >
                Goal Event
              </dt>
              <dd class="text-slate-200">{$userProfile.goal_event ?? "—"}</dd>
            </div>
            <div>
              <dt
                class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5"
              >
                Goal Date
              </dt>
              <dd class="text-slate-200">{$userProfile.goal_date ?? "—"}</dd>
            </div>
            {#if $userProfile.max_weekly_hours}
              <div>
                <dt
                  class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5"
                >
                  Max Weekly Hours
                </dt>
                <dd class="text-slate-200">{$userProfile.max_weekly_hours}h</dd>
              </div>
            {/if}
            {#if $userProfile.dietary_preference}
              <div>
                <dt
                  class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-0.5"
                >
                  Diet
                </dt>
                <dd class="text-slate-200">
                  {$userProfile.dietary_preference}
                </dd>
              </div>
            {/if}
          </dl>

          {#if !editingProfile}
            <button
              onclick={() => (editingProfile = true)}
              class="text-xs text-blue-500 hover:text-blue-700 font-medium transition"
            >
              Edit profile →
            </button>
          {:else}
            <div
              class="bg-slate-700/50 rounded-lg p-4 text-sm text-slate-300 border border-dashed border-slate-600"
            >
              Full profile editing coming in Day 6 — swimming skills, medical
              conditions, dietary preferences and more.
            </div>
            <button
              onclick={() => (editingProfile = false)}
              class="text-xs text-slate-400 hover:text-slate-200 transition"
            >
              Cancel
            </button>
          {/if}
        {:else}
          <p class="text-sm text-slate-400">
            No profile loaded. Make sure a user ID is set.
          </p>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── SECTION 2: AI Models ──────────────────────────────────────── -->
  <div class="card overflow-hidden">
    <button
      onclick={() => toggle("models")}
      class="w-full flex items-center justify-between p-5 text-left hover:bg-slate-700/50 transition"
    >
      <div class="flex items-center gap-3">
        <Cpu size={18} class="text-slate-400 shrink-0" />
        <span class="font-semibold text-slate-100">AI Models</span>
      </div>
      {#if openSection === "models"}
        <ChevronUp size={16} class="text-slate-400" />
      {:else}
        <ChevronDown size={16} class="text-slate-400" />
      {/if}
    </button>

    {#if openSection === "models"}
      <div class="px-5 pb-5 border-t border-slate-700 space-y-5 pt-4">
        {#if loading}
          <div class="space-y-3">
            <div class="h-9 bg-slate-700 rounded animate-pulse"></div>
            <div class="h-9 bg-slate-700 rounded animate-pulse"></div>
          </div>
        {:else}
          <!-- Analysis model -->
          <div class="space-y-1.5">
            <label
              for="model-analysis"
              class="text-xs font-semibold text-slate-400 uppercase tracking-wide"
            >
              Analysis Model
            </label>
            <p class="text-xs text-slate-400">
              Used for readiness analysis pipeline
            </p>
            <select
              id="model-analysis"
              bind:value={modelAnalysis}
              class="w-full rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200
                     bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
            >
              {#each MODEL_OPTIONS as group}
                <optgroup label={group.group}>
                  {#each group.options as opt}
                    <option value={opt.value}>{opt.label}</option>
                  {/each}
                </optgroup>
              {/each}
            </select>
            <p class="text-xs text-slate-500 font-mono truncate">
              {modelAnalysis}
            </p>
          </div>

          <!-- Planning model -->
          <div class="space-y-1.5">
            <label
              for="model-planning"
              class="text-xs font-semibold text-slate-400 uppercase tracking-wide"
            >
              Planning Model
            </label>
            <p class="text-xs text-slate-400">
              Used for training plan generation
            </p>
            <select
              id="model-planning"
              bind:value={modelPlanning}
              class="w-full rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200
                     bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
            >
              {#each MODEL_OPTIONS as group}
                <optgroup label={group.group}>
                  {#each group.options as opt}
                    <option value={opt.value}>{opt.label}</option>
                  {/each}
                </optgroup>
              {/each}
            </select>
            <p class="text-xs text-slate-500 font-mono truncate">
              {modelPlanning}
            </p>
          </div>

          <button
            onclick={saveModelConfig}
            disabled={savingModels}
            class="btn-primary flex items-center gap-2 disabled:opacity-60"
          >
            {#if savingModels}
              <span
                class="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"
              ></span>
              Saving…
            {:else}
              <Cpu size={14} />
              Save Model Config
            {/if}
          </button>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── SECTION 3: Data Sync ──────────────────────────────────────── -->
  <div class="card overflow-hidden">
    <button
      onclick={() => toggle("sync")}
      class="w-full flex items-center justify-between p-5 text-left hover:bg-slate-700/50 transition"
    >
      <div class="flex items-center gap-3">
        <RefreshCw size={18} class="text-slate-400 shrink-0" />
        <span class="font-semibold text-slate-100">Data Sync</span>
      </div>
      {#if openSection === "sync"}
        <ChevronUp size={16} class="text-slate-400" />
      {:else}
        <ChevronDown size={16} class="text-slate-400" />
      {/if}
    </button>

    {#if openSection === "sync"}
      <div class="px-5 pb-5 border-t border-slate-700 space-y-4 pt-4">
        <div class="flex items-center gap-2 text-sm text-slate-400">
          <RefreshCw size={14} class="text-slate-500" />
          <span
            >Last synced: <span class="text-slate-200 font-medium">—</span
            ></span
          >
        </div>

        <div class="bg-slate-700/50 rounded-lg p-4 space-y-2">
          <p class="text-sm font-medium text-slate-200">Garmin Connect</p>
          <p class="text-xs text-slate-400 leading-relaxed">
            Pulls HRV, sleep, body battery, training load, and activity data
            from your Garmin device via the Garmin Connect API.
          </p>
          <button
            onclick={triggerSync}
            disabled={syncLoading}
            class="mt-1 btn-primary flex items-center gap-2 disabled:opacity-60"
          >
            {#if syncLoading}
              <span
                class="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"
              ></span>
              Syncing…
            {:else}
              <RefreshCw size={14} />
              Sync Garmin Data
            {/if}
          </button>
        </div>
      </div>
    {/if}
  </div>

  <!-- ── SECTION 4: About ──────────────────────────────────────────── -->
  <div class="card overflow-hidden">
    <button
      onclick={() => toggle("about")}
      class="w-full flex items-center justify-between p-5 text-left hover:bg-slate-700/50 transition"
    >
      <div class="flex items-center gap-3">
        <Info size={18} class="text-slate-400 shrink-0" />
        <span class="font-semibold text-slate-100">About</span>
      </div>
      {#if openSection === "about"}
        <ChevronUp size={16} class="text-slate-400" />
      {:else}
        <ChevronDown size={16} class="text-slate-400" />
      {/if}
    </button>

    {#if openSection === "about"}
      <div class="px-5 pb-5 border-t border-slate-700 pt-4 space-y-3">
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between">
            <dt class="text-slate-400">Version</dt>
            <dd class="text-slate-200 font-mono">{APP_VERSION}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-slate-400">Backend</dt>
            <dd class="text-slate-200">FastAPI + SQLite</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-slate-400">Frontend</dt>
            <dd class="text-slate-200">SvelteKit 5 + Tailwind CSS v4</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-slate-400">AI Provider</dt>
            <dd class="text-slate-200">OpenRouter / Anthropic Claude</dd>
          </div>
        </dl>
        <p class="text-xs text-slate-300 pt-1">
          AI Fitness Coach — personal project. Not medical advice.
        </p>
      </div>
    {/if}
  </div>
</div>

<style>
  @keyframes fade-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  .animate-fade-in {
    animation: fade-in 0.25s ease-out both;
  }
  @keyframes slide-in {
    from {
      opacity: 0;
      transform: translateX(12px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  .animate-slide-in {
    animation: slide-in 0.2s ease-out both;
  }
</style>
