# iPhone Keyboard Composer Visible-Viewport Anchoring v2

## Summary

Changed mobile keyboard-active composer placement from bottom-gap anchoring to explicit visual-viewport top anchoring so iPhone Safari can keep the composer visible as soon as the input receives focus.

## Files Changed

- `frontend/src/components/Chat.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-26-iphone-keyboard-composer-visible-viewport-v2.md`

## Behavior Changed

- The chat composer DOM height is measured before positioning.
- Visual viewport metrics now set explicit CSS variables for viewport height, viewport offset, composer height, composer fixed top, and occluded bottom space.
- During mobile keyboard-active mode, the composer uses `position: fixed` with `top: var(--anam-composer-fixed-top)` instead of relying on `bottom`.
- The fixed top is computed as `visualViewport.offsetTop + visualViewport.height - composerHeight`.
- The message list reserves the measured occluded bottom space so the newest message can scroll above the fixed composer and keyboard.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Browser smoke check at 390x844 mobile viewport confirmed focus applies keyboard-active layout, fixed composer positioning, measured composer height, explicit composer top anchoring, and occluded bottom-space padding.

## Known Limitations

- Real iPhone Safari keyboard behavior still needs device verification.
- This patch does not add custom user-scrolled-up suppression; it preserves existing auto-scroll behavior.

## Follow-up Work

- Verify on iPhone Safari that tapping the input shows the composer immediately before typing.
- If the device still reports delayed `visualViewport` metrics, capture the reported CSS variable values from Safari remote inspection and tune the scheduled update windows.

## Project Anam Alignment Check

- This is frontend layout work for the Project Anam substrate.
- Does not change backend behavior, memory, prompts, guidance, model config, scheduler, research, Moltbook, web, image generation, or avatar behavior.
- Does not assign the entity a name, avatar, appearance, personality, or self-representation.
