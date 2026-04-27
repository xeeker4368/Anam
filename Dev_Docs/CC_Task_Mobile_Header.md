# CC Task: Fix Mobile Top Spacing

## What this is

On iPhone Safari, the chat content starts too close to the top and gets hidden under the URL bar. Add a header bar on mobile that creates visible separation.

## File to modify

- `frontend/src/App.jsx` — add a header element in the mobile layout
- `frontend/src/styles.css` — style the mobile header

## Change to `frontend/src/App.jsx`

In the mobile layout section, find the mobile return block. Add a header inside `mobile-content`, before the tab content. Replace this section:

```jsx
    return (
      <div className="app mobile">
        <div className="mobile-content">
          {activeTab === 'chat' && (
```

With:

```jsx
    return (
      <div className="app mobile">
        <div className="mobile-header">
          <span className="mobile-title">Tír</span>
          {activeConversationId && (
            <button onClick={handleCloseConversation} className="btn btn-small">
              Close
            </button>
          )}
          <button onClick={handleNewConversation} className="btn btn-small">
            New
          </button>
        </div>
        <div className="mobile-content">
          {activeTab === 'chat' && (
```

No other changes to App.jsx.

## Change to `frontend/src/styles.css`

Add these rules inside the mobile media query (before the closing `}`):

```css
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
```

## Verify

Open on iPhone. You should see a "Tír" header bar at the top with New/Close buttons. The first chat message should be fully visible below the header. The header should stay fixed at the top when scrolling.

## What NOT to do

- Do NOT remove the safe area insets from the previous fix — they still help with the notch
- Do NOT add the header to the desktop layout — desktop has the sidebar
