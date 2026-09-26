# Operations notes (load on demand)

Validated 2026-09-26 against CiteSpace 6.4.R2 Basic over live MCP stdio;
full receipts in docs/CITESPACE_INTEGRATION.md §"Validated functional run".

## Session and window lifetime

- An MCP client living in a transient agent shell takes the CiteSpace JVM
  down when that shell exits. A detached holder session survives, but its
  lifetime is finite (~17 min observed once, ~2 h another time) and the JVM
  can die silently. Before hand-back, verify with `citespace_status` that a
  `CiteSpace: Display Merged` window is visible; if the holder died, relaunch
  a fresh detached session that keeps its event loop alive.

## Windows and controls (JAB bridge)

- Window titles carry a suffix: `CiteSpace: Display Merged - (c) 2003-2026
  Chaomei Chen - Project Home: ...`. Prefix-match titles everywhere.
- The merged display toolbar exposes ~60 accessible elements, including the
  push button `Show/Hide Citation/Frequency Burst`. Clicking it round-trips,
  but on a run where burstness detection was never executed the toggle
  produces zero pixel change — burst overlays require running CiteSpace burst
  detection first.
- Starting a new run (`citespace_activate_research`) closes the previous
  run's idle display. Plan multi-dimension surveys as sequential runs and
  capture each view before activating the next.

## Screenshots

- Prefer `citespace_capture_research_view`. If grabbing the window rect
  directly, foreground it first (`ShowWindow(SW_RESTORE)` +
  `SetForegroundWindow`); otherwise the capture returns whatever window is on
  top.

## Counts honesty

- The native display count and the GraphML export can differ (observed
  N=94/E=513 native vs 94/485 exported). Always run
  `citespace_verify_native_counts`; when they differ, exported
  density/degree describe the exported graph only, and the report must say so.
