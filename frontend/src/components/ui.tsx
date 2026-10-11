/**
 * Presentational primitives shared by every panel.
 *
 * These exist so a card, a heading, and a state message look the same everywhere, and
 * so a colour is chosen from one list rather than re-picked in each component.
 */

import type { ReactNode } from 'react'

export function Panel({
  title,
  subtitle,
  action,
  children,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-[var(--color-ink)] uppercase">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-1 text-xs text-[var(--color-ink-muted)]">{subtitle}</p>
          ) : null}
        </div>
        {action}
      </header>
      {children}
    </section>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-[var(--color-surface-sunken)] ${className}`}
    />
  )
}

/**
 * The one place a fetch outcome is rendered.
 *
 * Every panel routes its loading, error, and empty cases here, which is what keeps
 * those three states from drifting apart between sections of the page.
 */
export function StateMessage({
  kind,
  message,
  onRetry,
}: {
  kind: 'loading' | 'error' | 'empty'
  message?: string
  onRetry?: () => void
}) {
  if (kind === 'loading') {
    return (
      <div role="status" aria-live="polite" className="py-6 text-center">
        <Skeleton className="mx-auto h-6 w-32" />
        <span className="sr-only">Loading</span>
      </div>
    )
  }

  if (kind === 'error') {
    const described = describeErrorFromMessage(message)
    return (
      <div role="alert" className="rounded-lg bg-[var(--color-danger)]/10 p-4 text-sm">
        <p className="font-medium text-[var(--color-danger)]">{described.title}</p>
        <p className="mt-1 text-[var(--color-ink-muted)]">{described.hint}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-surface-raised)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:outline-none"
          >
            Retry
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <div className="py-8 text-center text-sm text-[var(--color-ink-muted)]">
      {message ?? 'No usage recorded yet.'}
    </div>
  )
}

/**
 * Turn an error message back into the two-part form `StateMessage` shows.
 *
 * The hook owns the wording for a live error; this covers the case where only the
 * message survived, so an error is never rendered as a bare sentence.
 */
function describeErrorFromMessage(message: string | undefined): {
  title: string
  hint: string
} {
  if (!message) {
    return { title: 'Something went wrong', hint: 'No further detail was reported.' }
  }
  return { title: 'Could not load this data', hint: message }
}

export function Badge({
  tone,
  title,
  children,
}: {
  tone: 'neutral' | 'positive' | 'warning' | 'danger'
  title?: string
  children: ReactNode
}) {
  const tones: Record<string, string> = {
    neutral: 'bg-[var(--color-surface-sunken)] text-[var(--color-ink-muted)]',
    positive: 'bg-[var(--color-positive)]/12 text-[var(--color-positive)]',
    warning: 'bg-[var(--color-warning)]/12 text-[var(--color-warning)]',
    danger: 'bg-[var(--color-danger)]/12 text-[var(--color-danger)]',
  }
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  )
}
