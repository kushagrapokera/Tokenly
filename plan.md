# Universal AI Token Usage Tracker — plan.md

## 1. Project Overview

Build a local-first, unified AI token usage tracking platform that allows developers to monitor token consumption across different AI coding assistants, models, and providers.

The platform must track usage independently of the API keys, subscriptions, or model providers configured within each coding assistant.

The project is being developed incrementally, with one platform integration completed at a time.

**Current focus: Cline CLI**

---

## 2. Platform Integration Status

| Platform | Status | Priority |
|---|---|---|
| OpenCode | ✅ Done | Completed |
| Cline CLI | 🔄 In Progress | Current |
| Codex CLI | ⏳ Planned | Future |
| Claude Code | ⏳ Planned | Future |
| Antigravity | ⏳ Planned | Future |
| FreeBuff | ⏳ Planned | Future |

### Completed: OpenCode

The OpenCode integration is marked as completed.

Its intended capabilities include:

- Automatic collection of available token usage
- Daily, monthly, and yearly token statistics
- Model-wise token consumption
- Multiple provider support
- Free and paid model support
- Historical usage tracking
- Duplicate prevention
- Local data persistence

No additional OpenCode development is included in the current scope.

### Current: Cline CLI

The next objective is to add Cline CLI to the existing token tracking platform.

Cline CLI must integrate with the same unified usage tracking experience without requiring changes to existing OpenCode functionality.

---

## 3. Core Project Objectives

The platform must provide three primary capabilities:

### 3.1 Platform-Wise Token Usage

Track total tokens consumed by each supported AI coding platform independently.

For example:

| Platform | Total Tokens |
|---|---:|
| OpenCode | 2,500,000 |
| Cline CLI | 1,200,000 |
| Combined | 3,700,000 |

*Illustrative values.*

### 3.2 Time-Based Token Usage

Track token consumption across:

- Today
- Yesterday
- Last 7 days
- Current month
- Previous month
- Current year
- All-time usage
- Custom date ranges

Users must be able to view combined usage across supported platforms or filter by an individual platform.

### 3.3 Model-Wise Token Usage

Track token consumption separately for every model used within each platform.

Example:

| Platform | Model | Total Tokens |
|---|---|---:|
| OpenCode | Claude Sonnet | 900,000 |
| OpenCode | GPT | 600,000 |
| Cline CLI | Claude Sonnet | 450,000 |
| Cline CLI | Gemini | 300,000 |

The same model used in two different platforms must be tracked independently.

---

# 4. Cline CLI Integration Requirements

## 4.1 Automatic Cline CLI Detection

The application must automatically detect an existing Cline CLI installation and locate its available session history.

Requirements:

- Support Windows, Linux, and macOS.
- Detect the active Cline CLI data directory.
- Support default and custom data locations.
- Support compatible Cline CLI versions.
- Identify available session records.
- Work without modifying Cline CLI configuration.
- Work without requiring API keys.

If Cline CLI is not installed or no session data is available, the application must clearly communicate this.

## 4.2 Automatic Token Collection

The application must collect available token usage information from Cline CLI's local records or supported interfaces.

For each recorded model request, collect:

- Platform identifier
- Model identifier
- Provider identifier
- Input token count
- Output token count
- Timestamp
- Session identifier
- Unique usage identifier, where available

The application must distinguish actual usage events from repeated or cumulative records.

Token collection must not depend on the model's price.

## 4.3 Provider-Independent Tracking

Cline CLI supports multiple model providers.

The tracker should support token collection for models accessed through:

- Cline's own provider
- OpenAI
- Anthropic
- Google
- OpenRouter
- OpenAI-compatible providers
- Ollama and other supported local-model providers
- Additional Cline-compatible providers

Users must not be required to provide their provider API keys to the token tracker.

The tracker must use available usage metadata rather than assuming that every provider reports tokens identically.

## 4.4 Free and Paid Model Support

The tracker must support:

- Free hosted models
- Paid API models
- Subscription-based models
- Local models
- Third-party provider models

Free models must be tracked in the same way as paid models whenever reliable usage metadata is available.

The application must not exclude a model simply because its usage has no associated API cost.

If token metadata is unavailable, the application must indicate missing information rather than report an incorrect zero.

## 4.5 Historical Token Usage

The application must import available Cline CLI historical usage.

Expected behavior:

- Discover existing sessions.
- Collect available historical token records.
- Preserve their original timestamps.
- Associate tokens with the correct model and provider.
- Avoid duplicate historical records.
- Preserve imported data independently of Cline CLI.

Historical usage before tracker installation is limited to records still available locally.

## 4.6 Continuous Usage Tracking

The application must automatically detect new Cline CLI usage as it becomes available.

Expected behavior:

- Track newly created sessions.
- Track usage added to existing sessions.
- Recognize model changes.
- Recognize provider changes.
- Resume collection after application restarts.
- Avoid duplicate counting.
- Keep dashboard statistics updated.

The tracker must not interfere with active Cline CLI sessions.

## 4.7 Multiple Sessions and Model Switching

The application must support:

- Multiple Cline CLI sessions
- Resumed sessions
- Multiple models within a session
- Multiple providers within a session
- Interrupted sessions
- Retried model requests
- Concurrent sessions, where supported

Each usage record must be attributed to the correct model and platform.

## 4.8 Token Accuracy

The application must prioritize accuracy over completeness.

Requirements:

- Prefer reported token counts.
- Avoid duplicate usage.
- Handle incomplete usage records.
- Avoid double counting overlapping token categories.
- Distinguish unavailable counts from zero.
- Distinguish reported counts from estimated counts.
- Handle partial and interrupted responses.
- Avoid treating cumulative counters as individual requests.

For the initial release, the main token categories are:

- Input tokens
- Output tokens
- Combined total tokens

The system must use a consistent token accounting definition across OpenCode and Cline CLI.

---

# 5. Unified Dashboard Requirements

The existing dashboard must support both OpenCode and Cline CLI.

## 5.1 Overview

Display:

| Metric | Description |
|---|---|
| Today's Tokens | Combined tokens consumed today |
| Monthly Tokens | Combined tokens consumed this month |
| Yearly Tokens | Combined tokens consumed this year |
| All-Time Tokens | Combined historical token usage |

## 5.2 Platform Breakdown

Users must be able to view token consumption separately for:

- OpenCode
- Cline CLI

The dashboard must also show combined usage across both platforms.

## 5.3 Model Breakdown

Display:

- Platform
- Provider
- Model
- Input tokens
- Output tokens
- Total tokens
- Recorded request count

The dashboard must distinguish identical model names used through different providers.

## 5.4 Visualizations

The dashboard should provide:

- Daily token usage chart
- Monthly token usage chart
- Yearly token usage chart
- Platform usage comparison
- Model usage comparison
- Input versus output token breakdown

## 5.5 Filters

Users must be able to filter statistics by:

- Platform
- Provider
- Model
- Date range

Filters should work consistently across all supported platforms.

## 5.6 Integration Status

The dashboard must show:

- OpenCode integration status
- Cline CLI integration status
- Last successful data collection
- Whether historical records are available
- Whether usage data is incomplete
- Any collection errors

---

# 6. Data Persistence Requirements

The application must maintain its own local usage history.

Requirements:

- Preserve imported token records.
- Avoid duplicate counting.
- Support historical usage queries.
- Preserve data after source sessions are deleted.
- Support continued collection after application restarts.
- Keep usage from different platforms distinguishable.
- Maintain consistent model and provider identifiers.
- Support future platform integrations without losing existing records.

The application must not modify the original OpenCode or Cline CLI session data.

---

# 7. Privacy and Security Requirements

The application must:

- Operate locally by default.
- Never require users to provide model-provider API keys.
- Never collect or store provider credentials.
- Avoid collecting prompts and model responses.
- Avoid collecting source code.
- Access only information necessary for token usage tracking.
- Avoid modifying coding assistant configuration.
- Avoid intercepting model API traffic.
- Avoid disrupting normal coding assistant operations.

The tracker must remain independent of the user's existing provider authentication.

---

# 8. Out of Scope

The following features are excluded from the current Cline CLI integration:

- Cache hit and cache miss analytics
- Cache read and cache write token breakdowns
- API cost calculations
- Provider billing information
- Subscription quota tracking
- Rate-limit monitoring
- Cloud synchronization
- Team analytics
- Prompt analysis
- Source code analysis
- Additional coding assistant integrations

These features may be added in future releases.

---

# 9. Cline CLI Success Criteria

The Cline CLI integration is considered complete when:

- [ ] Cline CLI is automatically detected.
- [ ] Available historical usage is imported.
- [ ] New usage is collected automatically.
- [ ] Input tokens are tracked.
- [ ] Output tokens are tracked.
- [ ] Total tokens are calculated accurately.
- [ ] Daily usage statistics are available.
- [ ] Monthly usage statistics are available.
- [ ] Yearly usage statistics are available.
- [ ] Model-wise usage statistics are available.
- [ ] Provider-wise identification works.
- [ ] Free and paid models are supported wherever usage metadata exists.
- [ ] Multiple sessions are handled correctly.
- [ ] Model switching is handled correctly.
- [ ] Duplicate usage is prevented.
- [ ] Historical data is preserved.
- [ ] No API keys are required.
- [ ] Cline CLI configuration remains unchanged.
- [ ] Existing OpenCode tracking continues working.
- [ ] Combined OpenCode and Cline CLI statistics are accurate.
- [ ] Missing or incomplete usage is clearly indicated.

---

# 10. Project Completion Status

## OpenCode

**Status: DONE**

Marked completed for this project.

## Cline CLI

**Status: IN PROGRESS**

Current development target.

## Other Platforms

**Status: PLANNED**

Not included in the current development scope.

---

# 11. Final Project Goal

Create a unified, privacy-first AI coding token usage tracking platform that automatically monitors token consumption across multiple coding assistants.

The current release must support:

1. OpenCode — completed integration.
2. Cline CLI — current integration.

Users should be able to understand:

- How many tokens they consume overall.
- How many tokens they consume daily, monthly, and yearly.
- How many tokens each AI coding platform consumes.
- How many tokens each model consumes within each platform.

**The immediate goal is to complete Cline CLI integration without disrupting the existing OpenCode integration.**