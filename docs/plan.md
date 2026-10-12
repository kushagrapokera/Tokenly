# Universal AI Token Usage Tracker — plan.md

## 1. Project Overview

Build a unified, local-first AI token usage tracking platform that automatically monitors token consumption across different AI coding assistants, model providers, and AI models.

The platform allows users to understand their token consumption without modifying their existing coding assistant configurations.

The project follows an incremental integration approach, reusing existing functionality whenever possible.

**Completed integrations:**
- OpenCode
- Cline CLI

**Current integrations:**
- Claude Code
- Codex CLI

**Primary goal:** Extend the existing application to support Claude Code and Codex CLI, including their native models and supported third-party providers.

---

## 2. Platform Integration Status

| Platform | Status | Scope |
|---|---|---|
| OpenCode | ✅ COMPLETED | Existing integration |
| Cline CLI | ✅ COMPLETED | Existing integration |
| Claude Code | 🔄 PLANNED FOR IMPLEMENTATION | Current scope |
| Codex CLI | 🔄 PLANNED FOR IMPLEMENTATION | Current scope |
| Antigravity | ⏳ FUTURE | Not included |
| FreeBuff | ⏳ FUTURE | Not included |

### Completed Integrations

**OpenCode — DONE**

The existing OpenCode integration must remain functional.

**Cline CLI — DONE**

The existing Cline CLI integration must remain functional.

Neither completed integration should be rebuilt as part of the current project scope.

---

## 3. Core Objectives

The tracker must support:

1. Automatic token collection from Claude Code and Codex CLI.
2. Tracking token usage independently of the configured model provider.
3. Daily, monthly, yearly, and all-time usage statistics.
4. Model-wise token consumption within each platform.
5. Provider-wise token consumption within each platform.
6. Historical token usage import.
7. Automatic tracking of new usage.
8. Combined usage statistics across all completed integrations.
9. Support for native and compatible third-party models.
10. Minimal setup with no API keys or request proxies required.

The tracker must use the existing shared analytics infrastructure wherever compatible.

---

# 4. Claude Code Integration Requirements

## 4.1 Automatic Detection

The tracker must automatically detect an existing Claude Code installation and locate available usage history.

Requirements:

- Support Windows, Linux, and macOS.
- Detect default and supported custom data locations.
- Recognize supported Claude Code versions.
- Identify available session records.
- Detect new sessions automatically.
- Operate without changing Claude Code configuration.
- Operate without requiring Anthropic or third-party provider API keys.

If Claude Code is not installed or its local history is unavailable, display the appropriate tracking status.

## 4.2 Native Claude Model Support

The tracker must support Claude models used through Claude Code.

Model families may include:

- Claude Opus
- Claude Sonnet
- Claude Haiku
- Other supported Claude models

Usage must be attributed to the actual model identifier recorded by Claude Code.

Different versions of a model must remain distinguishable when their identifiers differ.

## 4.3 Third-Party Provider Support

The tracker must support compatible third-party model providers and gateways used with Claude Code.

Target providers include:

- Anthropic
- OpenRouter
- Amazon Bedrock
- Google Vertex AI
- DeepSeek
- GLM / Z.AI
- Kimi / Moonshot AI
- Other compatible API gateways

Support is conditional on the provider and model configuration actually being compatible with the installed Claude Code version.

The tracker must not assume every model can be used directly through Claude Code.

### Provider Requirements

- Identify the configured provider when reliable local metadata is available.
- Identify the actual model used.
- Support provider-specific model identifiers.
- Track usage without requiring provider credentials.
- Support free and paid models where reliable usage metadata exists.
- Avoid incorrect provider attribution.
- Preserve unknown provider values when identification is not reliable.

## 4.4 Claude Code Token Tracking

Track:

- Input tokens
- Output tokens
- Total tokens
- Model identifier
- Provider identifier
- Session identifier
- Usage timestamp

Token usage must be attributed to the correct model, including sessions where model switching occurs.

The tracker must distinguish actual token usage from estimates.

## 4.5 Claude Code Historical Usage

The tracker must:

- Import available historical sessions.
- Preserve original usage timestamps.
- Track historical model usage.
- Prevent duplicate imports.
- Preserve imported records independently of Claude Code.
- Handle incomplete or missing historical metadata.

Historical tracking is limited to usage records that remain available and accessible.

## 4.6 Claude Code Continuous Tracking

The tracker must:

- Automatically recognize new usage.
- Support resumed sessions.
- Support model switching.
- Support provider switching.
- Handle interrupted requests.
- Handle updated usage records.
- Resume tracking after application restarts.
- Avoid duplicate token counting.

---

# 5. Codex CLI Integration Requirements

## 5.1 Automatic Detection

The tracker must automatically detect Codex CLI and locate available usage history.

Requirements:

- Support Windows, Linux, and macOS.
- Detect default and supported custom storage locations.
- Recognize supported Codex CLI versions.
- Identify available session records.
- Automatically track new sessions.
- Require no changes to Codex CLI configuration.
- Require no OpenAI or third-party provider API keys.

## 5.2 Native OpenAI Model Support

The tracker must support OpenAI models used through Codex CLI.

This includes supported GPT and Codex-oriented models.

Requirements:

- Identify the actual model used.
- Preserve model version distinctions.
- Track input and output tokens.
- Support model switching.
- Support available historical usage.
- Work independently of whether authentication uses a subscription or an API key.

The tracker must not assume that subscription usage is equivalent to API billing usage.

## 5.3 Third-Party Provider Support

The tracker must support compatible third-party providers configured in Codex CLI.

Target providers include:

- OpenAI
- OpenRouter
- DeepSeek
- GLM / Z.AI
- Kimi / Moonshot AI
- Other supported OpenAI-compatible providers
- Compatible local model providers

The actual supported combinations depend on the installed Codex CLI version and provider configuration.

### Provider Requirements

- Identify the actual provider where possible.
- Identify the configured model.
- Preserve provider-specific model names.
- Support free and paid models.
- Track usage without accessing provider credentials.
- Avoid hardcoding assumptions about model providers.
- Handle unavailable provider metadata.
- Handle provider-specific token reporting differences.

## 5.4 Codex CLI Token Tracking

Track:

- Input tokens
- Output tokens
- Total tokens
- Provider
- Model
- Session
- Timestamp

The tracker must account for cases where Codex exposes cumulative token totals, incremental usage events, or both.

Cumulative totals must not be counted as independent requests.

## 5.5 Codex CLI Historical Usage

The tracker must:

- Import available historical sessions.
- Identify token usage records.
- Preserve model and provider attribution.
- Prevent duplicate imports.
- Preserve collected data after original history is deleted.
- Handle incomplete records.

## 5.6 Codex CLI Continuous Tracking

The tracker must:

- Detect newly recorded usage.
- Track active and resumed sessions.
- Support model changes.
- Support provider changes.
- Handle interrupted requests.
- Handle cumulative usage updates.
- Resume tracking after restarts.
- Prevent duplicate counting.

---

# 6. Unified Provider and Model Tracking

## 6.1 Platform, Provider, and Model Identification

Every usage record must distinguish:

**Platform:** The AI coding assistant where the usage occurred.

**Provider:** The service or gateway through which the model was accessed.

**Model:** The actual AI model used.

Example:

| Platform | Provider | Model |
|---|---|---|
| Claude Code | Anthropic | Claude Sonnet |
| Claude Code | OpenRouter | DeepSeek |
| Claude Code | Z.AI | GLM |
| Claude Code | Moonshot | Kimi |
| Codex CLI | OpenAI | GPT |
| Codex CLI | OpenRouter | DeepSeek |
| Codex CLI | Z.AI | GLM |
| Codex CLI | Moonshot | Kimi |

These are illustrative target scenarios, subject to actual compatibility and reliable usage reporting.

## 6.2 Provider Independence

The tracker must not depend on:

- A specific model provider
- A specific API key
- Model pricing
- Subscription billing
- A particular API endpoint
- Whether a model is free or paid

The tracker must collect available usage information from the coding assistant's local records or supported interfaces.

## 6.3 Same Model Across Multiple Platforms

A model may be used through multiple coding assistants.

Example:

| Platform | Provider | Model | Tokens |
|---|---|---|---:|
| OpenCode | OpenRouter | DeepSeek | 500,000 |
| Cline CLI | OpenRouter | DeepSeek | 300,000 |
| Claude Code | OpenRouter | DeepSeek | 200,000 |
| Codex CLI | OpenRouter | DeepSeek | 400,000 |

The tracker must support:

- Individual platform usage
- Individual provider usage
- Individual model usage
- Combined usage across platforms

The same usage event must never be counted twice.

---

# 7. Time-Based Token Analytics

The application must provide:

- Today's usage
- Yesterday's usage
- Last 7 days
- Current month
- Previous month
- Current year
- All-time usage
- Custom date ranges

Users must be able to view these statistics across all supported platforms or filter by platform, provider, and model.

Calendar-based calculations must use the user's selected timezone.

---

# 8. Unified Dashboard Requirements

## 8.1 Overview

Display:

- Total tokens today
- Total tokens this month
- Total tokens this year
- All-time token consumption

These metrics must include usage from:

- OpenCode
- Cline CLI
- Claude Code
- Codex CLI

Only actual collected usage should contribute to totals.

## 8.2 Platform Breakdown

Display token usage separately for each platform.

Users must be able to compare token consumption across coding assistants.

## 8.3 Provider Breakdown

Display token usage grouped by provider.

Examples:

- Anthropic
- OpenAI
- OpenRouter
- DeepSeek
- Z.AI
- Moonshot

Unknown providers must be represented accurately rather than guessed.

## 8.4 Model Breakdown

Display:

- Platform
- Provider
- Model
- Input tokens
- Output tokens
- Total tokens
- Recorded request count, where available

## 8.5 Visualizations

Required charts:

- Daily token usage
- Monthly token usage
- Yearly token usage
- Platform comparison
- Provider comparison
- Model comparison
- Input/output breakdown

## 8.6 Filters

Support:

- Platform
- Provider
- Model
- Date range

Filters must work across all four platforms.

## 8.7 Integration Status

Display:

- Platform detected or not detected
- Tracking active or inactive
- Last successful synchronization
- Available historical data
- Collection errors
- Incomplete token reporting

---

# 9. Historical Data and Persistence

The tracker must maintain its own persistent local usage history.

Requirements:

- Preserve collected records.
- Avoid duplicate imports.
- Support incremental synchronization.
- Preserve records after source history deletion.
- Support multiple coding assistants.
- Support multiple providers and models.
- Maintain consistent timestamp handling.
- Keep platform-specific identifiers distinct.
- Preserve existing OpenCode and Cline CLI data.

The tracker must not modify source session data.

---

# 10. Accuracy and Reliability Requirements

Accuracy is a core requirement.

The tracker must:

- Prefer reported usage over estimates.
- Avoid double counting.
- Distinguish cumulative and incremental token counts.
- Handle interrupted sessions.
- Handle retries.
- Handle model switching.
- Handle provider switching.
- Handle missing usage metadata.
- Avoid double counting cached or reasoning tokens.
- Distinguish unknown values from zero.
- Preserve model attribution whenever reliable.
- Report incomplete usage coverage.

If the platform does not expose enough information to determine exact token usage, the application must clearly communicate that limitation.

The tracker must not fabricate token counts.

---

# 11. Reusability Requirements

The Claude Code and Codex CLI integrations must extend the existing application.

The following existing capabilities must be reused wherever compatible:

- Application infrastructure
- Collector interfaces
- Token normalization
- Deduplication
- Historical synchronization
- Local database
- Aggregation logic
- Backend API
- Dashboard
- Filtering and visualization
- Error handling

Only platform-specific functionality should be added when required.

The application must not create separate token tracking systems for Claude Code and Codex CLI.

Existing OpenCode and Cline CLI functionality must remain intact.

---

# 12. Privacy and Security

The application must:

- Operate locally by default.
- Require no provider API keys.
- Avoid reading or storing credentials.
- Avoid collecting prompt contents.
- Avoid collecting source code.
- Avoid collecting model response contents.
- Use read-only access to coding assistant data.
- Avoid modifying existing configurations.
- Avoid intercepting API requests.
- Avoid routing model traffic through a proxy.
- Minimize stored information.

Users must remain in control of their locally collected analytics.

---

# 13. Out of Scope

The following are excluded from the current release:

- Cache hit/miss analytics
- Cache read/write breakdown dashboards
- Cost estimation
- Subscription quota tracking
- Provider rate-limit tracking
- Cloud synchronization
- Team usage analytics
- Prompt content analysis
- Source code analysis
- Antigravity integration
- FreeBuff integration

Cache and reasoning token metadata may be used internally when necessary to avoid incorrect totals, but dedicated analytics for those categories are deferred.

---

# 14. Success Criteria

## Claude Code

- [ ] Claude Code is automatically detected.
- [ ] Available historical usage is imported.
- [ ] New usage is collected automatically.
- [ ] Native Claude models are tracked.
- [ ] Compatible third-party providers are supported.
- [ ] Input and output tokens are tracked.
- [ ] Daily, monthly, and yearly statistics work.
- [ ] Model-wise statistics work.
- [ ] Provider-wise statistics work.
- [ ] Model switching is handled.
- [ ] Duplicate counting is prevented.
- [ ] No API keys or configuration changes are required.

## Codex CLI

- [ ] Codex CLI is automatically detected.
- [ ] Available historical usage is imported.
- [ ] New usage is collected automatically.
- [ ] Native OpenAI models are tracked.
- [ ] Compatible third-party providers are supported.
- [ ] Input and output tokens are tracked.
- [ ] Daily, monthly, and yearly statistics work.
- [ ] Model-wise statistics work.
- [ ] Provider-wise statistics work.
- [ ] Cumulative token reporting is handled correctly.
- [ ] Duplicate counting is prevented.
- [ ] No API keys or configuration changes are required.

## Unified Platform

- [ ] OpenCode remains functional.
- [ ] Cline CLI remains functional.
- [ ] Claude Code integrates with the existing application.
- [ ] Codex CLI integrates with the existing application.
- [ ] All four platforms use the same analytics system.
- [ ] Combined platform usage is accurate.
- [ ] Provider and model filters work.
- [ ] Existing historical data is preserved.
- [ ] No duplicate infrastructure is introduced.
- [ ] Existing functionality passes regression testing.

---

# 15. Final Project Status

| Integration | Status |
|---|---|
| OpenCode | ✅ DONE |
| Cline CLI | ✅ DONE |
| Claude Code | 🔄 NEXT |
| Codex CLI | 🔄 NEXT |
| Antigravity | ⏳ FUTURE |
| FreeBuff | ⏳ FUTURE |

---

# 16. Final Project Goal

Extend the existing universal AI token usage tracker to support Claude Code and Codex CLI alongside the completed OpenCode and Cline CLI integrations.

The platform must support native models and compatible third-party providers such as OpenRouter, DeepSeek, GLM, and Kimi wherever reliable token usage data is available.

Users must be able to monitor:

1. Total token consumption across all supported coding assistants.
2. Daily, monthly, yearly, and all-time token usage.
3. Platform-wise token usage.
4. Provider-wise token usage.
5. Model-wise token usage.

**The final result must be one unified, reusable, local-first token analytics platform—not four separate tracking applications.**