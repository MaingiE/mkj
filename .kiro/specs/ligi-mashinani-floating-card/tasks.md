# Implementation Plan: Ligi Mashinani Floating Card

## Overview

All changes are confined to `templates/public/home.html`. The implementation adds the card HTML into `{% block content %}`, the CSS (layout, keyframes, responsive styles, reduced-motion) into `{% block extra_css %}`, and the JavaScript (countdown, dismiss, toss animation, button fade-in) into `{% block extra_js %}`. No Django views, models, or URLs are modified.

## Tasks

- [x] 1. Add floating card HTML structure to `{% block content %}`
  - [x] 1.1 Insert `#ligi-float-card` div at the end of `{% block content %}`, before the closing `{% endblock %}`
    - Add the wrapper div with `id="ligi-float-card"`, `role="complementary"`, `aria-label="Ligi Mashinani registration"`, and `aria-live="polite"`
    - Add the dismiss `<button class="ligi-card__dismiss" aria-label="Close registration card">` with `<span aria-hidden="true">&times;</span>` inside
    - Add `<div class="ligi-card__body">` containing:
      - `<h2 class="ligi-card__title">Ligi Mashinani 2026/2029 Season</h2>`
      - `<p class="ligi-card__sub">Register your ward team today</p>`
      - The countdown block: `<div class="ligi-card__countdown" id="ligi-countdown">` with a `<noscript>-- days --:--:--</noscript>` child and `<span id="ligi-countdown-display">-- days --:--:--</span>`
      - The CTA anchor: `<a href="/ligi/register/" class="ligi-card__btn" id="ligi-register-btn">Register Now</a>`
    - _Requirements: 1.1, 1.3, 1.4, 1.8, 3.5, 3.6, 4.3, 5.1, 5.6_

- [x] 2. Add CSS — card layout, positioning, and brand colours
  - [x] 2.1 Add base card layout rules inside `{% block extra_css %}`
    - Set `#ligi-float-card` to `position: fixed; z-index: 9000; bottom: 2rem; right: 1.5rem; max-width: 420px; background: #0a2f5c; color: #ffffff; border-radius: 12px; padding: 1.25rem 1.5rem; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.45)`
    - Style `.ligi-card__dismiss` at `position: absolute; top: 0.5rem; right: 0.75rem; background: transparent; border: none; color: #E8B91E; font-size: 1.5rem; cursor: pointer; width: 32px; height: 32px; line-height: 1`
    - Style `.ligi-card__title` at `font-size: 1.25rem; margin: 0 0 0.4rem; color: #E8B91E`
    - Style `.ligi-card__sub` at `font-size: 0.9rem; margin: 0 0 0.75rem`
    - Style `.ligi-card__countdown` at `font-size: 1.1rem; font-weight: bold; color: #E8B91E; margin-bottom: 1rem; letter-spacing: 0.04em`
    - Style `.ligi-card__btn` at `display: inline-block; padding: 0.6rem 1.4rem; background: #E8B91E; color: #0a2f5c; font-weight: 700; font-size: 1rem; border-radius: 6px; text-decoration: none; min-width: 44px; min-height: 44px; line-height: 1.6; outline-offset: 3px`
    - Add `.ligi-card__btn:hover` with `transform: scale(1.07); background: #f5cc4a; transition: transform 200ms, background 200ms`
    - Add `.ligi-card__btn:focus-visible` with `outline: 2px solid #ffffff; outline-offset: 3px`
    - _Requirements: 1.1, 1.5, 4.2, 4.5, 4.6, 5.1_

  - [x] 2.2 Add `@keyframes ligiToss` entry animation
    - Define `@keyframes ligiToss` with:
      - `0%` → `transform: translateX(110vw) translateY(-80vh) rotate(22deg); opacity: 0`
      - `60%` → position near final with -12px Y overshoot and `rotate(-3deg); opacity: 1`
      - `80%` → overshoot recovery, slight positive Y overshoot
      - `100%` → `transform: translate(0, 0) rotate(0deg); opacity: 1`
    - Apply to `#ligi-float-card`: `animation: ligiToss 900ms cubic-bezier(0.22, 1, 0.36, 1) both`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.3 Add `@keyframes ligiBtnPulse` and `@keyframes ligiBtnFadeIn`
    - Define `@keyframes ligiBtnPulse` cycling `box-shadow` between a minimal and prominent gold glow state on a `1600ms infinite` loop
    - Define `@keyframes ligiBtnFadeIn`: `from { opacity: 0 }` → `to { opacity: 1 }`; duration 300ms
    - Apply `ligiBtnPulse` to `.ligi-card__btn` once the card has settled (use a `.ligi-settled` class added by JS — style `.ligi-settled .ligi-card__btn { animation: ligiBtnFadeIn 300ms ease forwards, ligiBtnPulse 1600ms ease-in-out 300ms infinite }`)
    - Set initial state on `#ligi-register-btn`: `opacity: 0` so the button is invisible until JS triggers the settled state
    - _Requirements: 4.1, 4.4_

  - [x] 2.4 Add responsive styles for viewport < 480px
    - Add `@media (max-width: 479px)` block:
      - `#ligi-float-card { bottom: 1rem; left: 1rem; right: 1rem; max-width: none; width: calc(100% - 2rem) }`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 2.5 Add `@media (prefers-reduced-motion: reduce)` block
    - Override `#ligi-float-card { animation: none !important; transform: none !important; opacity: 1 !important }`
    - Override `.ligi-card__btn { animation: none !important; opacity: 1 !important }`
    - _Requirements: 2.6_

- [x] 3. Checkpoint — verify CSS renders correctly
  - Open `home.html` in a browser and confirm the card appears in the bottom-right corner, uses the correct brand colours, and the button is initially hidden. Resize to < 480px and confirm the full-width bottom-anchored layout. Ask the user if anything looks off before continuing.

- [x] 4. Add JavaScript — countdown timer, dismiss control, toss animation, button fade-in
  - [x] 4.1 Add the `formatCountdown` pure function and `LIGI_DEADLINE` constant inside `{% block extra_js %}`
    - Define `const LIGI_DEADLINE = new Date('2025-12-31T23:59:59+03:00')` at the top of the script block
    - Implement `formatCountdown(ms)`: return `null` when `ms <= 0`; otherwise compute `dd`, `hh`, `mm`, `ss` using integer division, zero-pad each with `String(n).padStart(2, '0')`, return `"DD days HH:MM:SS"` string
    - _Requirements: 3.1, 3.3, 3.4_

  - [ ]* 4.2 Write property test for `formatCountdown` (Property 1)
    - Set up a Jest + fast-check test file at `static/js/__tests__/ligiCard.test.js` (or equivalent path matching the project's JS test setup); export `formatCountdown` from an inline module or a thin helper file so it can be imported
    - **Property 1: Countdown formatter correctness**
    - **Validates: Requirements 3.1, 3.3**
    - Use `fc.integer({ min: 1, max: Number.MAX_SAFE_INTEGER })` to assert result matches `/^\d{2,} days \d{2}:\d{2}:\d{2}$/` and all field values are in range; use `fc.integer({ min: Number.MIN_SAFE_INTEGER, max: 0 })` to assert result is `null`; run at least 100 iterations each

  - [x] 4.3 Implement `startCountdown()` and wire the interval to the DOM
    - Implement `startCountdown()`: call `setInterval` every 1000ms; compute `msRemaining = LIGI_DEADLINE - Date.now()`; call `formatCountdown(msRemaining)`; if result is `null`, set `countdownEl.textContent = 'Registration Closed'` and hide `#ligi-register-btn`; otherwise set `countdownEl.textContent = result`
    - Fire one immediate tick before the first interval fires so the display is never blank
    - _Requirements: 3.2, 3.3, 3.6, 1.7_

  - [x] 4.4 Implement `dismissCard()` and wire it to the dismiss button
    - Implement `dismissCard()`: set `card.style.transition = 'opacity 300ms ease'; card.style.opacity = '0'`; after 300ms timeout, set `card.style.display = 'none'` and `card.setAttribute('aria-hidden', 'true')`
    - Add a `click` event listener on `.ligi-card__dismiss` that calls `dismissCard()`
    - Add a `keydown` listener on `.ligi-card__dismiss` that calls `dismissCard()` when `event.key === 'Enter' || event.key === ' '`
    - _Requirements: 5.2, 5.3, 5.4, 5.5_

  - [x] 4.5 Implement `startTossAnimation()` and `showBtn()` with Web Animations API
    - Implement `startTossAnimation()`: guard with `if (window.matchMedia('(prefers-reduced-motion: reduce)').matches)` — if true, skip animation and call `showBtn()` immediately; otherwise use `card.animate([{...keyframe 0...}, {...keyframe 100...}], { duration: 900, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'forwards' })` with intermediate keyframes mirroring the CSS `ligiToss` values; attach `.finished.then(() => showBtn())` on the returned animation object; fall back to direct class add if `element.animate` is not supported
    - Implement `showBtn()`: add class `ligi-settled` to `#ligi-float-card` (triggers the CSS fade-in + pulse); call `startCountdown()`
    - Wire `initCard()` to `window.addEventListener('load', () => setTimeout(startTossAnimation, 50))`
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 4.1, 4.4_

- [x] 5. Checkpoint — verify full animation sequence
  - Load the homepage and confirm: card flies in from top-right within 100ms of load, overshoots, settles within 1500ms, button fades in and begins pulsing. Enable `prefers-reduced-motion` in OS settings and confirm the card appears instantly with no animation. Ask the user if questions arise.

- [x] 6. Verify accessibility requirements
  - [x] 6.1 Audit ARIA attributes and keyboard navigation in the HTML
    - Confirm `#ligi-float-card` has `role="complementary"` and `aria-label="Ligi Mashinani registration"`
    - Confirm `.ligi-card__dismiss` has `aria-label="Close registration card"` and the `&times;` span has `aria-hidden="true"`
    - Confirm `#ligi-register-btn` is an `<a>` with `href="/ligi/register/"` — not a `<button>` — so it is natively focusable and operable by keyboard Enter
    - Confirm dismiss button has explicit `type="button"` to prevent accidental form submission
    - _Requirements: 5.5, 5.6, 4.3_

  - [x] 6.2 Verify contrast ratios and focus indicator styles in CSS
    - Check white (`#ffffff`) on `#0a2f5c` background → target ≥ 4.5:1 (actual ~10.5:1 ✓)
    - Check `#0a2f5c` text on `#E8B91E` button → target ≥ 4.5:1 (actual ~7.2:1 ✓)
    - Check `#E8B91E` dismiss icon on `#0a2f5c` → target ≥ 3:1 (actual ~4.8:1 ✓)
    - Confirm `.ligi-card__btn:focus-visible` has `outline: 2px solid #ffffff` with at least 3:1 contrast against `#E8B91E` button background (white on gold: ~2.1:1 — if this fails, change outline colour to `#0a2f5c` which gives ~7.2:1 ✓)
    - _Requirements: 4.2, 4.6, 5.1_

  - [x] 6.3 Verify touch target and overflow constraints
    - Confirm `.ligi-card__btn` has `min-width: 44px; min-height: 44px` (WCAG 2.5.5)
    - Confirm `.ligi-card__dismiss` has rendered width ≥ 24px and height ≥ 24px
    - Confirm `#ligi-float-card` has `overflow: hidden` to prevent horizontal document scroll
    - _Requirements: 5.1, 6.3, 6.4_

- [x] 7. Final checkpoint — full accessibility and layout review
  - Tab through the card with keyboard only: confirm Tab reaches the dismiss button, pressing Enter/Space dismisses the card; confirm Tab reaches the Register Now link, pressing Enter navigates to `/ligi/register/`
  - Test at 320px viewport width: confirm all text ≥ 14px, no horizontal scroll, card fills width with 1rem margins on each side
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- The CSS animation in task 2.2 and the JS animation in task 4.5 both define the same `ligiToss` motion — the JS implementation (Web Animations API) is the authoritative runtime path; the CSS `@keyframes` in task 2.2 is the fallback/reference definition used when JS drives the same values
- `LIGI_DEADLINE` in task 4.1 is the single change point for any future deadline update
- Property tests require fast-check as a dev dependency only — no new runtime scripts are added to the template
- Checkpoints in tasks 3, 5, and 7 represent manual verification gates, not automated tests

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "4.2"] },
    { "id": 3, "tasks": ["4.3", "4.4", "6.1", "6.2", "6.3"] },
    { "id": 4, "tasks": ["4.5"] }
  ]
}
```
