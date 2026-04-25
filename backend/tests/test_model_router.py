"""Integration tests for model router, compression, and context portability."""

import asyncio
import inspect
import json
import traceback

from agents.caveman import compress
from agents.context import ConversationContext
from agents.model_router import get_model_client
from db.cost_logger import _estimate_cost

TEST_PROMPT = (
    "Athlete HRV: 38ms (baseline 52ms, -27%). Sleep score: 61. "
    "Body battery morning: 34. ACWR: 1.31. "
    "Yesterday: 75min tempo run, RPE 8.\n"
    'Respond ONLY with JSON: {"readiness_score": int 0-100, "gate": str, "one_line_summary": str}'
)

MESSAGES = [
    {"role": "system", "content": "You are a sports-science AI. Reply only with valid JSON."},
    {"role": "user", "content": TEST_PROMPT},
]

results: list[tuple[str, bool]] = []
total_cost = 0.0


async def test_openrouter() -> None:
    global total_cost
    client = get_model_client("openrouter/anthropic/claude-3-5-sonnet-20241022")
    resp = await client.complete(MESSAGES, json_mode=True)

    cost = _estimate_cost(resp.model, resp.prompt_tokens, resp.completion_tokens)
    total_cost += cost

    print(f"  backend:    {resp.backend}")
    print(f"  model:      {resp.model}")
    print(f"  tokens_in:  {resp.prompt_tokens}")
    print(f"  tokens_out: {resp.completion_tokens}")
    print(f"  latency_ms: {resp.latency_ms}")
    print(f"  cost_usd:   ${cost:.6f}")

    parsed = json.loads(resp.content)
    print(f"  readiness:  {parsed.get('readiness_score')}")
    print(f"  gate:       {parsed.get('gate')}")

    assert resp.total_tokens > 0, "total_tokens should be > 0"


async def test_ollama() -> None:
    global total_cost
    client = get_model_client("ollama/llama3.2:3b")
    resp = await client.complete(MESSAGES, json_mode=True)

    cost = _estimate_cost(resp.model, resp.prompt_tokens, resp.completion_tokens)
    total_cost += cost

    print(f"  backend:    {resp.backend}")
    print(f"  model:      {resp.model}")
    print(f"  tokens_in:  {resp.prompt_tokens}")
    print(f"  tokens_out: {resp.completion_tokens}")
    print(f"  latency_ms: {resp.latency_ms}")
    print(f"  cost_usd:   ${cost:.6f}")

    try:
        parsed = json.loads(resp.content)
        print(f"  readiness:  {parsed.get('readiness_score')}")
        print(f"  gate:       {parsed.get('gate')}")
    except json.JSONDecodeError:
        print(f"  (response not valid JSON, raw: {resp.content[:200]})")

    assert resp.total_tokens > 0, "total_tokens should be > 0"


def test_compression() -> None:
    sample = """Please analyze the following athlete data carefully. I would like you to provide
a detailed assessment of readiness and training recommendations.

Heart Rate Variability: 38 milliseconds, which is well below the baseline of
52 milliseconds, representing a 27% decrease. Resting Heart Rate is 55 beats
per minute, which is elevated compared to the 7-day average of 50 beats per
minute. The training stress score from yesterday's session was 145, which is
quite high for this athlete's fitness level.

The acute chronic workload ratio is currently 1.31, which is above the
recommended range of 0.8 to 1.3. This suggests the athlete may be
accumulating fatigue faster than they can recover. Body battery readings
show a minimum of 15 and maximum of 34, suggesting poor recovery overnight.

Sleep data shows a sleep score of 61, with sleep duration of 390 minutes.
Deep sleep was only 45 minutes and REM sleep was 68 minutes. The athlete
reported perceived effort of 8 out of 10 for yesterday's zone 3 tempo run
lasting 75 minutes, followed by zone 1 cooldown for 15 minutes.

Note that the athlete has a marathon goal event scheduled for September 2026.
Keep in mind that they have reported mild knee discomfort. It is important
to consider training load management. You should provide specific recovery
recommendations including nutrition, sleep, and active recovery protocols.

Recent activity data: {"activityId": 12345, "distance": 12500.5, "duration": 4500,
"calories": 850, "averageHR": 162, "maxHR": 178, "steps": 14200,
"trainingEffect": 4.2, "vo2max": 45.0}

Make sure to factor in the cumulative training load from the past 7 days
when making your assessment. As an AI fitness coach, prioritize athlete
safety and long-term development over short-term performance gains."""

    compressed, ratio = compress(sample)
    print(f"  original_chars:   {len(sample)}")
    print(f"  compressed_chars: {len(compressed)}")
    print(f"  ratio:            {ratio:.1%}")
    assert ratio > 0.1, f"Expected >10% compression, got {ratio:.1%}"


def test_context_portability() -> None:
    ctx = ConversationContext(
        agent_type="analysis",
        user_id="test-user-001",
        date_range="2026-04-17 to 2026-04-23",
        compressed_summary="hrv down 27%, acwr 1.31, bb low, gate amber",
        pinned_facts={
            "goal_event": "marathon",
            "goal_date": "2026-09-15",
            "weeks_to_goal": 21,
            "medical_conditions": "mild knee discomfort",
        },
        recent_readiness_scores=[72, 68, 65, 70, 60, 55, 58],
        last_training_gate="amber",
        model_used="openrouter/anthropic/claude-3-5-sonnet",
        total_tokens_used=3500,
        created_at="2026-04-24T10:00:00Z",
    )

    serialised = ctx.to_db_json()
    restored = ConversationContext.from_db_json(serialised)

    assert restored.agent_type == ctx.agent_type
    assert restored.pinned_facts == ctx.pinned_facts
    assert restored.recent_readiness_scores == ctx.recent_readiness_scores
    assert restored.last_training_gate == ctx.last_training_gate

    injection = restored.to_system_injection()
    print(f"  round-trip: OK ({len(serialised)} bytes)")
    print(f"  injection preview:\n{injection[:300]}")


async def main() -> None:
    tests = [
        ("test_openrouter", test_openrouter),
        ("test_ollama", test_ollama),
        ("test_compression", test_compression),
        ("test_context_portability", test_context_portability),
    ]

    for name, fn in tests:
        print(f"\n{'=' * 50}")
        print(f"Running: {name}")
        print("=" * 50)
        try:
            if inspect.iscoroutinefunction(fn):
                await fn()
            else:
                fn()
            results.append((name, True))
            print(f"  >>> PASS")
        except Exception as exc:
            results.append((name, False))
            print(f"  >>> FAIL: {exc}")
            traceback.print_exc()

    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print("=" * 50)
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    passed_count = sum(1 for _, p in results if p)
    print(f"\n  {passed_count}/{len(results)} passed")
    print(f"  Total estimated cost: ${total_cost:.6f}")


if __name__ == "__main__":
    asyncio.run(main())
