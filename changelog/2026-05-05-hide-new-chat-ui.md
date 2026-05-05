# Hide New Chat UI

## Summary

Removed the user-facing New Conversation/New button from the frontend so the interface no longer suggests ChatGPT-style isolated chats.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/styles.css`

## Behavior Changed

- The desktop sidebar no longer shows a New Conversation button.
- The mobile header no longer shows a New button.
- Backend conversation/session APIs and lifecycle behavior remain unchanged.
- Existing conversation/session IDs can still be used internally for provenance, chunking, debug traces, artifact/message links, and lifecycle management.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Existing conversation list and Close controls still expose backend session boundaries.
- This patch does not add active conversation checkpointing.

## Follow-Up Work

- Implement active conversation checkpointing in a separate backend-focused patch if approved.
- Revisit visible conversation/session language later if the UI should further emphasize continuity.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved backend conversation/session lifecycle for provenance and memory processing.
- Did not change memory architecture, database schema, API routes, or chunking.
- Did not modify `soul.md`.
- Did not rename `tir/`.
