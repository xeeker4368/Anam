# CC Task: Fix Mobile Layout (Replace Mobile CSS)

## What this is

The mobile CSS has conflicting height/overflow rules causing the input bar to disappear and content to render behind the URL bar. This replaces the entire mobile section of styles.css with a clean implementation.

## File to modify

- `frontend/src/styles.css`

## Change

Find the entire mobile section — everything from `/* --- Mobile layout --- */` to the end of the file. **Delete all of it** and replace with:

```css
/* --- Mobile layout --- */
@media (max-width: 767px) {
  .app.mobile {
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    padding-top: env(safe-area-inset-top);
  }

  .mobile-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #16213e;
    border-bottom: 1px solid #2a2a4a;
    flex-shrink: 0;
  }

  .mobile-title {
    font-size: 18px;
    font-weight: 600;
    color: #7faacc;
    flex: 1;
  }

  .mobile-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .mobile-content > main,
  .mobile-content > aside {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    width: 100%;
  }

  .mobile-content .chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .mobile-content .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    min-height: 0;
  }

  .mobile-content .input-area {
    flex-shrink: 0;
    padding: 10px 12px;
  }

  .mobile-content .input-area textarea {
    font-size: 16px;
  }

  .mobile-sidebar {
    width: 100%;
    border-right: none;
    overflow-y: auto;
  }

  .mobile-debug {
    width: 100%;
    border-left: none;
    overflow-y: auto;
  }

  .tab-bar {
    display: flex;
    border-top: 1px solid #2a2a4a;
    background: #16213e;
    flex-shrink: 0;
    padding-bottom: env(safe-area-inset-bottom);
  }

  .tab-btn {
    flex: 1;
    padding: 12px 0;
    background: transparent;
    color: #888;
    border: none;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }

  .tab-btn.active {
    color: #7faacc;
    border-top: 2px solid #7faacc;
  }

  .tab-btn:hover {
    color: #999;
  }

  .message {
    max-width: 100%;
  }

  .debug-toggle {
    display: none;
  }
}
```

Key fixes:
- `100dvh` instead of just `100vh` — `dvh` is the dynamic viewport height on iOS that accounts for the URL bar
- `min-height: 0` on every flex child in the chain — without this, flex items won't shrink below their content size, which is what causes the input to get pushed off screen
- Removed `overflow-y: auto` from `.mobile-content` — only the `.messages-container` should scroll
- `flex-shrink: 0` on `.input-area` — the input bar never shrinks

## Verify

With `npx vite --host` running, open on iPhone:

1. The header "Tír" should be visible at the top below the URL bar
2. Messages should be in the middle and scrollable
3. The text input and Send button should be visible at the bottom, above the tab bar
4. The tab bar (Convos / Chat / Debug) should be at the very bottom
5. Send a message — after the response streams in, the input should still be visible

## What NOT to do

- Do NOT change App.jsx — only the CSS changes
- Do NOT change the desktop CSS above the mobile section
