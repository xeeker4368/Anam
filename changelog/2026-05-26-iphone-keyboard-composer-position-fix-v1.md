# iPhone Keyboard Composer Position Fix v1

## Summary

Moved mobile keyboard handling earlier in the focus lifecycle so the chat composer can stay visible above the iOS keyboard before the user starts typing.

## Files Changed

- `frontend/src/components/Chat.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-26-iphone-keyboard-composer-position-fix-v1.md`

## Behavior Changed

- Chat now updates visual viewport CSS variables immediately on input focus and on `visualViewport` resize/scroll events.
- Focus handling schedules repeated viewport reads during the iOS keyboard animation instead of waiting for typing/input events.
- Mobile chat applies a `keyboard-active` class while the composer is focused.
- In mobile keyboard-active state, the composer is fixed above the measured visual viewport bottom gap.
- The message list reserves composer and keyboard space so the latest message can stay visible above the composer.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Browser smoke check at 390x844 mobile viewport confirmed the input focus path applies keyboard-active layout, fixed composer positioning, and visual viewport CSS variables.

## Known Limitations

- Real iPhone Safari keyboard behavior still requires manual device verification.
- This patch keeps existing auto-scroll behavior; it does not add user-scrolled-up suppression.

## Follow-up Work

- Verify on iPhone Safari that the composer is visible immediately on focus before typing.
- Revisit landscape behavior later if it matters for household use.

## Project Anam Alignment Check

- This is frontend layout work for the Project Anam substrate.
- Does not change backend behavior, memory, prompts, guidance, model config, scheduler, research, Moltbook, web, image generation, or avatar behavior.
- Does not assign the entity a name, avatar, appearance, personality, or self-representation.
