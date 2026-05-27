# iPhone Keyboard Chat Viewport Fix v1

## Summary

Improved the mobile chat viewport so iPhone Safari keyboard opening keeps the composer usable and nudges the latest message back into view.

## Files Changed

- `frontend/index.html`
- `frontend/src/components/Chat.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-26-iphone-keyboard-chat-viewport-fix-v1.md`

## Behavior Changed

- Mobile app shell now uses dynamic viewport units where supported instead of relying only on the older full-height chain.
- Mobile chat messages get extra bottom padding and scroll padding so the last message is not hidden behind the composer.
- Mobile chat composer is sticky inside the chat shell and includes safe-area bottom padding.
- Chat scrolls to the newest message after input focus and after `visualViewport` resize/scroll events, which covers iOS keyboard open/close behavior.
- The viewport meta tag now includes `viewport-fit=cover` so safe-area inset handling works cleanly on iOS.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Browser smoke check at desktop viewport.
- Browser smoke check at 390x844 mobile viewport confirmed the mobile shell, sticky composer, scrollable message region, and mobile tab bar render.

## Known Limitations

- The final keyboard behavior still needs manual verification on iPhone Safari because desktop browser automation cannot reproduce the iOS keyboard.
- This patch does not add custom “user scrolled up” suppression; existing chat behavior already auto-scrolls on new messages.

## Follow-up Work

- Run the manual iPhone Safari checklist before go-live: focus input, send a message, stream a reply, background/return, and close keyboard.
- Revisit rotation behavior later if iPhone landscape use becomes important.

## Project Anam Alignment Check

- This is frontend layout work for the Project Anam substrate.
- Does not change backend behavior, memory, prompts, guidance, model config, scheduler, research, Moltbook, web, image generation, or avatar behavior.
- Does not assign the entity a name, avatar, appearance, personality, or self-representation.
