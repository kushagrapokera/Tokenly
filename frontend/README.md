# Tokenly dashboard

The React front end for Tokenly. It reads the local API and never talks to anything else:
no accounts, no telemetry, no remote calls.

## Running it

Start the backend first, then this dev server:

```bash
# in the project root
python main.py          # serves the API on http://127.0.0.1:8000

# in frontend/
npm install
npm run dev             # serves the dashboard on http://localhost:5173
```

The dev server proxies `/api` to the backend, so the browser only ever talks to one
origin. Point it elsewhere with `TOKENLY_API_URL=http://127.0.0.1:9000 npm run dev`.

For a production build, `npm run build` writes static files to `dist/`. Any static file
server will do; nothing in the bundle needs a server of its own.

## Layout

| Path | Concern |
|---|---|
| `src/api/types.ts` | the response shapes the backend returns |
| `src/api/client.ts` | every call to `fetch`, in one place |
| `src/api/errors.ts` | turning a failed response into a typed error |
| `src/lib/format.ts` | number and timestamp formatting |
| `src/hooks/useAsyncData.ts` | loading / ready / error as one value |
| `src/components/` | the panels and charts |
| `src/test/fixtures.ts` | response fixtures shaped like the real API |

## Commands

| Command | Purpose |
|---|---|
| `npm run dev` | dev server with the API proxy |
| `npm run build` | type-check and build to `dist/` |
| `npm run test` | run the Vitest suite once |
| `npm run test:watch` | re-run tests on change |
| `npm run typecheck` | TypeScript only |
| `npm run lint` | oxlint |

## Notes

The dashboard sends its own timezone with every request. The backend defaults to UTC
when one is absent, which would put "today" on the wrong calendar day for most of the
world; sending the browser's zone means the dashboard's idea of today is the user's.
