# CC Task: Fix iOS Safe Area

## What this is

On iPhone, the chat content starts behind the URL bar. Add safe area insets so content stays in the visible area.

## Files to modify

- `frontend/index.html` — add viewport-fit=cover
- `frontend/src/styles.css` — add safe area padding

## Change to `frontend/index.html`

Replace the viewport meta tag:

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

## Change to `frontend/src/styles.css`

In the mobile media query section, add padding to the app container and tab bar. Find the `.app.mobile` rule and replace it with:

```css
  .app.mobile {
    flex-direction: column;
    padding-top: env(safe-area-inset-top);
  }
```

Find the `.tab-bar` rule and replace it with:

```css
  .tab-bar {
    display: flex;
    border-top: 1px solid #2a2a4a;
    background: #16213e;
    flex-shrink: 0;
    padding-bottom: env(safe-area-inset-bottom);
  }
```

## Verify

Open on iPhone. The first message in the chat should be fully visible below the URL bar. The tab bar at the bottom should not be hidden behind the home indicator.

## What NOT to do

- Do NOT change any other files
- Do NOT add a fixed header bar — the safe area padding is sufficient
