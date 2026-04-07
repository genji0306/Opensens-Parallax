# V3 Frontend Test Readiness

Date: 2026-04-01  
Scope: `Parallax-V2/frontend`

## 1. Automated Gate

Run one command:

```bash
cd frontend
npm run verify
```

This runs:

- `npm run typecheck`
- `npm test`
- `npm run build`

## 2. Feature Flags

Optional `.env` flags:

- `VITE_FRONTEND_V3_ENABLED=true|false`
- `VITE_V3_ROUTING_ENABLED=true|false`

Expected behavior:

- If `VITE_V3_ROUTING_ENABLED=false`, `/v3/*` redirects to `/`.
- Debate simulation runs route to `/v3/debate/:runId` only when V3 routing is enabled.

## 3. Manual QA Smoke Checklist

1. Open `/` and verify Command Center loads recent runs.
2. Open a debate-style run (`ossr_sim_*`) from Command Center or History.
3. Confirm it opens Debate Analysis (not legacy AIS project) when V3 routing is enabled.
4. Open an AIS run (`ais_run_*`) and confirm legacy project detail still loads.
5. In Draft stage detail, confirm section placeholder note appears when only section count is available:
   - "Section titles unavailable from backend artifact."
6. Open `/v3`, `/v3/debate/:runId`, `/v3/governance`, `/v3/project/:projectId` and verify each page renders.
7. Verify no repeated 404 loop for AIS-only endpoints when viewing debate runs.

## 4. Known Non-Blocking Build Warnings

- Vite reports mixed dynamic/static imports for `debug` and `pipeline` stores.
- These are chunking warnings only; they do not block build/test readiness.
