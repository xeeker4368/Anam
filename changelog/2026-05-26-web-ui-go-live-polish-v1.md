# Web UI Go-Live Polish v1

## Summary

Polished the web UI so chat remains the primary household interface while developer-facing panels stay available but less dominant.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/index.html`
- `frontend/src/components/Chat.jsx`
- `frontend/src/components/RegistryPanel.jsx`
- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-26-web-ui-go-live-polish-v1.md`

## Behavior Changed

- Visible legacy `Tír` labels were replaced with `Project Anam` as the app/substrate label.
- Assistant message labels now say `Assistant` instead of `A`.
- Desktop debug/status/media panel starts collapsed so chat is the clear default experience.
- Mobile navigation now prioritizes `Chat`, `History`, `Media`, `Status`, and `Debug`.
- Mobile header now keeps the active household user visible and selectable when multiple users exist.
- Registry-facing labels were softened into `Media & Artifacts` / generated media wording.
- Touch targets and narrow-screen media/image generation form layout were improved.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Browser smoke check at desktop and 390x844 mobile viewport

## Known Limitations

- This patch does not add a polished Admin Settings area.
- This patch does not implement real login/session auth.
- This patch does not change backend capabilities, model configuration, image generation behavior, scheduler behavior, or artifact semantics.

## Follow-up Work

- Add a dedicated Admin Settings / Model Selection design and implementation later if needed.
- Run an in-browser desktop and iPhone smoke test against the live local app before go-live.

## Project Anam Alignment Check

- Uses `Project Anam` only as the substrate/app label.
- Does not assign the entity a name, avatar, appearance, personality, or self-representation.
- Keeps image generation framed as ordinary generated media artifacts.
- Does not alter prompts, guidance, model config, memory, research, Moltbook, web, scheduler, or backend behavior.
