# ATLAS V7 — Light / Dark Theme Toggle

Presentation-only enhancement.

## Added
- Top-bar Light / Dark button.
- Full light theme for page background, cards, tables, navigation, dialogs, forms, badges and status panels.
- Theme choice stored in browser localStorage under `atlas.v7.theme`.
- Last selected theme is restored on next load.
- Public helper: `window.ATLAS_THEME.get()` and `window.ATLAS_THEME.set('light'|'dark')`.

## Preservation
No trading, research, scoring, risk, learning, cloud, canary or stage logic is changed.
TradingView widget internals remain provider-controlled so the page theme cannot accidentally break chart rendering.
