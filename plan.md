# OpenCode Token Usage Tracker — Project Plan

## 1. Project Overview

Build a local-first application that automatically tracks token usage across different AI models used through **OpenCode**, regardless of the model provider or API key configuration.

The application will provide a centralized dashboard where users can view their total token consumption, analyze usage over different time periods, and identify how many tokens each model has consumed.

The tracker should work without requiring users to modify their existing OpenCode configuration or provide API keys.

The project will initially support **OpenCode only**, with the possibility of integrating additional AI coding platforms in the future.

---

## 2. Project Objectives

The primary objectives are:

1. Track total token consumption through OpenCode.
2. Track token usage on a daily, monthly, and yearly basis.
3. Track token consumption separately for every model used within OpenCode.
4. Support models accessed through different providers.
5. Support both free and paid models.
6. Automatically collect available token usage information.
7. Preserve historical usage data for long-term analysis.
8. Provide a simple and intuitive dashboard.

---

## 3. Core Features

### 3.1 Total Token Usage

Display the total number of tokens consumed through OpenCode.

The application should track:

- Input tokens
- Output tokens
- Total tokens consumed

Token counts should be based on usage reported by OpenCode wherever available.

### 3.2 Time-Based Token Tracking

Users should be able to view their token consumption across different periods.

Supported periods:

- Today
- Yesterday
- Last 7 days
- Current month
- Previous month
- Current year
- All-time usage
- Custom date range

The application should correctly aggregate usage based on the user's selected timezone.

### 3.3 Model-Wise Token Tracking

Track token usage independently for each model used through OpenCode.

For every model, display:

- Model name
- Provider name
- Input tokens
- Output tokens
- Total tokens consumed
- Number of recorded requests

If a user switches between models within the same OpenCode session, the application should attribute usage to the correct model.

### 3.4 Multi-Provider Support

The tracker should work independently of the provider used within OpenCode.

Examples include:

- OpenAI
- Anthropic
- Google
- OpenRouter
- Ollama
- Other OpenCode-supported providers

Users should not need to provide API keys to the tracker.

The application should distinguish between models with identical names accessed through different providers.

### 3.5 Free and Paid Model Support

The application must support token tracking for:

- Free hosted models
- Paid API models
- Subscription-based models
- Locally hosted models
- Third-party provider models

Token usage tracking must not depend on whether a model is free or paid.

If a provider does not expose token usage information, the application must clearly indicate that the usage data is unavailable rather than displaying an incorrect count.

### 3.6 Automatic Usage Collection

The application should automatically collect available token usage information from OpenCode's local session data or supported local interfaces.

Expected behavior:

- No manual token entry
- No API key requirements
- No API proxy configuration
- No modifications to OpenCode
- No interruption to normal OpenCode usage

The tracker should operate independently of the user's existing OpenCode setup.

### 3.7 Historical Usage Tracking

The application should display historical usage wherever records are available.

Expected behavior:

- Import available usage history when first installed.
- Preserve collected usage for future reference.
- Continue tracking new usage.
- Prevent duplicate counting.
- Retain previously collected usage even if OpenCode removes older session records.

Historical usage before installation is limited to data that remains available.

### 3.8 Automatic Updates

The application should update token statistics as new usage information becomes available.

Users should not need to manually refresh or reimport their session history.

The tracker should resume tracking after application restarts without duplicating existing records.

---

## 4. Dashboard Requirements

### 4.1 Overview

The main dashboard should display:

| Metric | Description |
|---|---|
| Today's Tokens | Tokens consumed today |
| Monthly Tokens | Tokens consumed during the current month |
| Yearly Tokens | Tokens consumed during the current year |
| All-Time Tokens | Total available historical token consumption |

### 4.2 Model Usage Breakdown

Display model-wise token usage.

| Model | Provider | Input Tokens | Output Tokens | Total |
|---|---|---:|---:|---:|
| Claude Sonnet | Anthropic | 120,000 | 30,000 | 150,000 |
| GPT | OpenAI | 90,000 | 20,000 | 110,000 |
| Gemini | Google | 70,000 | 15,000 | 85,000 |

*The values above are illustrative.*

### 4.3 Usage Visualizations

The dashboard should provide:

- Daily token usage chart
- Monthly token usage chart
- Yearly token usage chart
- Model-wise token usage comparison
- Input versus output token comparison

### 4.4 Filtering

Users should be able to filter usage by:

- Date range
- Model
- Provider

### 4.5 Tracking Status

The dashboard should indicate:

- Whether OpenCode is detected
- Whether usage tracking is active
- Last successful data update
- Whether usage records are incomplete or unavailable

---

## 5. Data Accuracy Requirements

Accurate token counting is a core requirement.

The application should:

- Prefer actual usage information reported by OpenCode.
- Avoid counting the same usage multiple times.
- Handle sessions containing multiple models.
- Distinguish missing usage from zero usage.
- Handle incomplete sessions and interrupted requests.
- Avoid double counting overlapping token categories.
- Distinguish reported token counts from estimated counts.
- Clearly communicate limitations in the available usage data.

The initial focus is input tokens, output tokens, and their combined total.

Additional token categories may be supported in the future.

---

## 6. Privacy and User Experience

The application should:

- Operate locally by default.
- Access only the information necessary for usage tracking.
- Avoid collecting prompts, responses, or source code.
- Never request or store model-provider API keys.
- Avoid modifying OpenCode session data.
- Require minimal setup.
- Work without disrupting OpenCode.
- Provide clear error messages when usage information cannot be collected.

---

## 7. Out of Scope

The following features are not included in the initial version:

- Cache hit and cache miss tracking
- Cache read and cache write analytics
- Token cost calculations
- API billing information
- Subscription quota monitoring
- Rate-limit tracking
- Cloud synchronization
- Multi-user and team analytics
- AI model performance comparisons
- Integration with coding assistants other than OpenCode

These may be considered in future versions.

---

## 8. Future Expansion

The project should eventually support other AI coding platforms, such as:

- Codex CLI
- Claude Code
- Cline CLI
- Antigravity
- FreeBuff

The long-term objective is to create a unified token usage tracking platform where users can compare token consumption across multiple coding assistants and models.

However, **no additional platform integrations are part of the current scope**.

---

## 9. Success Criteria

The OpenCode Token Usage Tracker will be considered successful when:

- [ ] It detects an existing OpenCode installation.
- [ ] It collects available token usage automatically.
- [ ] It tracks usage across different model providers.
- [ ] It supports free and paid models.
- [ ] It displays total token consumption.
- [ ] It displays daily token consumption.
- [ ] It displays monthly token consumption.
- [ ] It displays yearly token consumption.
- [ ] It displays token usage separately for each model.
- [ ] It imports available historical usage.
- [ ] It preserves collected history.
- [ ] It prevents duplicate counting.
- [ ] It operates without API keys or changes to OpenCode configuration.
- [ ] It clearly indicates incomplete or unavailable token data.
- [ ] It provides a functional and easy-to-use dashboard.

---

## 10. Project Goal

Develop a reliable, lightweight, privacy-focused application that allows developers to understand **how many tokens they consume through OpenCode, when they consume them, and which AI models consume them**.

The application should provide accurate and accessible token usage statistics without interfering with the user's existing OpenCode workflow.

This OpenCode-focused version will form the foundation for a future all-in-one AI coding token usage tracker.