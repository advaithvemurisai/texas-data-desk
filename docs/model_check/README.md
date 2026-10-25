# Week-1 model test

Picks the free models (docs/PLAN.md, week-1 checks). Ten throwaway questions, one per known
data trap, run by a single SQL agent (`tdd-model-check`) against the live warehouse built from
the 2026-10-17 snapshots. One run per model, so this is a screen, not a benchmark. The
questions are not part of the eval set and must not be reused in it.

Run 2026-10-25 (UTC). Result files: `*.json` in this folder.

## Results

| Model | Correct | Requests | Tokens | Plain-text turns | Median s/question | Stopped by |
| --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash-lite | **10/10** | 28 | 143k | 0 | 2 | (none) |
| qwen/qwen3.8-27b (Groq) | 9/10 | 31 | 158k | 0 | 139 | q04: request over the per-request limit |
| openai/gpt-oss-120b (Groq) | 5/9 | 53 | 283k | 29 | 175 | 200k tokens/day after q08 |
| gemini-3.5-flash | 1/2 | 12 | 67k | 0 | 39 | 20 requests/day |
| gemini-3.8-flash | 0/1 | 0 | 0 | 0 | | 20 requests/day (used up by smoke tests) |

No model returned a wrong number. Every miss was a quota stop, a request size limit, or
(gpt-oss-120b) running out of steps after answering in plain text instead of calling a tool.

## Free-tier limits measured

Groq: response headers and error messages. Gemini: AI Studio rate-limit page (ai.dev/rate-limit),
read 2026-10-25; the test run peaked at 19 requests/minute on Flash-Lite (one 429).

| Model | Per minute | Per day |
| --- | --- | --- |
| gemini-3.8-flash | 5 requests, 250k tokens | 20 requests |
| gemini-3.5-flash (served as gemini-3.6-flash) | 5 requests, 250k tokens | 20 requests |
| gemini-3.5-flash-lite | 15 requests, 250k tokens | 500 requests |
| openai/gpt-oss-120b (Groq) | 8,000 tokens | 1,000 requests, 200,000 tokens |
| qwen/qwen3.8-27b (Groq) | 7,000 input / 1,000 output tokens | not hit |

## What this means for the design

- **Gemini Flash (3.5, 3.8) cannot be the workhorse.** 20 requests a day is two or three
  questions. Flash-Lite is the only Gemini model with room for the orchestrator and workers.
- **Groq rejects any single request bigger than the per-minute limit** (HTTP 413), not just
  rate-limits it. q04 failed on both Groq models because one agent read all four cities' quirks
  notes. One worker per city, as planned, keeps each request small; the verifier must likewise
  see one city's notes at a time and stay well under ~6k input tokens per request.
- **Flash-Lite's 500 requests a day is the eval budget.** At 8–10 calls per question, that is
  ~50 questions a day across all agents. The full eval as planned (~9,000 calls) would take
  2–3 weeks of quota, so dev runs use 1 run per question and 3 runs only for final results.
- **gpt-oss-120b's 200k tokens a day** is about 5 questions in this one-agent setup. A verifier
  makes fewer, smaller calls, but the full eval (~9,000 calls) still needs several days or a
  second provider (Cerebras serves the same model).
- **gpt-oss-120b often answered in plain text** instead of calling a tool (29 times in 9
  questions). Not yet tried: `tool_choice: "required"`, which may fix it.
- Each question cost ~5–14k tokens per request because the system prompt (definitions + schema,
  ~6.4k tokens) is resent every step. Trimming it or caching answers matters on every provider.
