# Design Document — Ligi Mashinani Floating Card

## Overview

This document describes the technical design for the `ligi-mashinani-floating-card` feature — a floating call-to-action overlay added directly to `templates/public/home.html` that invites ward team managers to register for the Ligi Mashinani 2026/2029 season.

The feature is **purely frontend**: HTML, CSS, and vanilla JavaScript injected into the existing Django template blocks. No new views, models, URLs, or migrations are required. All code lives inside the blocks the template already exposes (`{% block extra_css %}`, `{% block content %}`, `{% block extra_js %}`).

### Goals

- Surface the registration CTA prominently without disrupting the existing hero section.
- Use a physics-inspired toss animation that grabs attention but respects reduced-motion preferences.
- Show a live countdown timer so urgency is immediately clear.
- Stay entirely within the project's existing asset stack — no new libraries.
- Meet WCAG 2.1 AA accessibility requirements for interactive controls.

---

## Architecture

The feature has three layers, all self-contained within `home.html`:

```
┌─────────────────────────────────────────────────────────────┐
│  templates/public/home.html                                 │
│                                                             │
│  {% block extra_css %}                                      │
│    <style>  <!-- Card CSS + keyframes + media queries -->   │
│  {% endblock %}                                             │
│                                                             │
│  {% block content %}                                        │
│    <!-- Existing hero HTML … -->                            │
│    <!-- ↓ APPENDED ↓ -->                                    │
│    <div id="ligi-float-card"> … </div>                      │
│  {% endblock %}                                             │
│                                                             │
│  {% block extra_js %}                                       │
│    <script> <!-- Countdown + dismiss + animation JS -->     │
│  {% endblock %}                                             │
└─────────────────────────────────────────────────────────────┘
```

The card element is a `position: fixed` overlay rendered above all hero content. It interacts with no Django context variables and requires no AJAX calls.

---

## Components and Interfaces

### 1. Card HTML Structure (`#ligi-float-card`)

```html
<div id="ligi-float-card"
     role="complementary"
     aria-label="Ligi Mashinani registration"
     aria-live="polite">

  <!-- Dismiss control -->
  <button class="ligi-card__dismiss"
          aria-label="Close registration card">
    <span aria-hidden="true">&times;</span>
  </button>

  <!-- Card body -->
  <div class="ligi-card__body">
    <h2 class="ligi-card__title">Ligi Mashinani 2026/2029 Season</h2>
    <p class="ligi-card__sub">Register your ward team today</p>

    <!-- Countdown -->
    <div class="ligi-card__countdown" id="ligi-countdown">
      <noscript>-- days --:--:--</noscript>
      <span id="ligi-countdown-display">-- days --:--:--</span>
    </div>

    <!-- CTA button — plain <a> so it works without JS -->
    <a href="/ligi/register/"
       class="ligi-card__btn"
       id="ligi-register-btn">
      Register Now
    </a>
  </div>
</div>
```

**Key structural decisions:**
- The element uses `role="complementary"` + `aria-label` so screen readers announce it as a landmark region.
- The countdown has a `<noscript>` sibling fallback and a non-empty placeholder (`-- days --:--:--`) so the element is never blank before JS runs.
- The Register button is an `<a href>` — not a `<button>` with a JS click handler — ensuring navigation works even with JS disabled.

### 2. CSS Layer (`{% block extra_css %}`)

All CSS is appended at the end of the `{% block extra_css %}` style block. Class prefix `ligi-card__` namespaces styles to avoid collisions with existing rules.

#### Z-index

The existing hero section reaches a maximum of `z-index: 6` (`.hero-brand-tl`). The card uses:

```css
#ligi-float-card { z-index: 9000; }
```

This places it above the hero, and below the preloader (`z-index: 99999` in `base.html`), so it never covers the loading screen.

#### Layout / positioning

```
Viewport ≥ 480px                 Viewport < 480px
────────────────                 ────────────────
position: fixed                  position: fixed
bottom: 2rem                     bottom: 1rem
right: 1.5rem                    left: 1rem; right: 1rem
max-width: 420px                 width: calc(100% - 2rem)
```

The right-offset desktop position was chosen (rather than centered) because the hero headline occupies the center column, so a right-anchored card avoids covering the primary text.

#### Keyframes

Three keyframe rules drive the animation pipeline:

| Name | Purpose |
|---|---|
| `@keyframes ligiToss` | Initial toss: flies in from top-right corner, overshoots, settles |
| `@keyframes ligiBtnPulse` | Continuous button pulse after card settles |
| `@keyframes ligiBtnFadeIn` | Button entrance after card settles |

`ligiToss` outline:

```
0%    translateX(110vw) translateY(-80vh) rotate(22deg) opacity(0)
60%   near final pos + slight overshoot (-12px Y) rotate(-3deg) opacity(1)
80%   overshoot recovery
100%  translate(0,0) rotate(0deg) opacity(1)
```

Total duration: 900ms — within the 1500ms limit, leaving headroom for the browser's compositing.

#### Reduced-motion

```css
@media (prefers-reduced-motion: reduce) {
  #ligi-float-card {
    animation: none !important;
    transform: none !important;
    opacity: 1 !important;
  }
  .ligi-card__btn { animation: none !important; }
}
```

The card renders instantly in its settled state when the user has requested reduced motion.

#### Brand colours

| Token | Value | Where used |
|---|---|---|
| Deep blue | `#0a2f5c` | Card background |
| Gold | `#E8B91E` | Countdown digits, dismiss button hover, title accent |
| White | `#ffffff` | Body text, button label |
| Button bg | `#E8B91E` | Register button background (gold on deep blue context) |

Contrast ratios:
- White on `#0a2f5c`: ~10.5:1 ✓ (WCAG AA)
- `#0a2f5c` text on `#E8B91E` button: ~7.2:1 ✓ (WCAG AA)
- Gold `#E8B91E` dismiss icon on `#0a2f5c` card: ~4.8:1 ✓

### 3. JavaScript Layer (`{% block extra_js %}`)

All JS is appended at the end of `{% block extra_js %}`. The script is wrapped in a `DOMContentLoaded`-safe IIFE.

#### Constants

```javascript
const LIGI_DEADLINE = new Date('2025-12-31T23:59:59+03:00');
```

This is the only value that needs to change when the deadline is updated.

#### Module responsibilities

```
ligiFloatCard.js (inline script)
├── initCard()          — entry point, called on window 'load'
├── startTossAnimation() — triggers element.animate() / class toggle
├── showBtn()           — fades in Register button after toss settles
├── startCountdown()    — setInterval every 1000ms
├── formatCountdown()   — pure function: ms → "DD days HH:MM:SS"
└── dismissCard()       — fade-out + display:none + aria-hidden
```

#### Countdown logic

```javascript
function formatCountdown(msRemaining) {
  if (msRemaining <= 0) return null; // signals "Registration Closed"
  const totalSecs = Math.floor(msRemaining / 1000);
  const ss = totalSecs % 60;
  const mm = Math.floor(totalSecs / 60) % 60;
  const hh = Math.floor(totalSecs / 3600) % 24;
  const dd = Math.floor(totalSecs / 86400);
  const pad = n => String(n).padStart(2, '0');
  return `${pad(dd)} days ${pad(hh)}:${pad(mm)}:${pad(ss)}`;
}
```

`formatCountdown` is a pure function — it takes a millisecond value and returns a string (or `null` when expired). This makes it independently testable without a DOM.

#### Animation sequencing

```
window 'load' event
  └─ 50ms delay (rAF / setTimeout)
       └─ startTossAnimation()     [900ms]
            └─ animation 'finish' callback
                 └─ showBtn()      [300ms fade-in]
                      └─ startCountdown()
```

Using the Web Animations API's `animation.finished` Promise (or `onfinish` callback) to trigger the button appearance ensures sequencing is driven by actual animation completion, not a guessed timeout.

#### Dismiss behaviour

```javascript
function dismissCard() {
  card.style.transition = 'opacity 300ms ease';
  card.style.opacity = '0';
  setTimeout(() => {
    card.style.display = 'none';
    card.setAttribute('aria-hidden', 'true');
  }, 300);
}
```

No `localStorage`, `sessionStorage`, or cookie writes. A full page reload always shows the card.

---

## Data Models

No server-side data models are involved. The single piece of runtime "data" is the deadline constant:

```
LIGI_DEADLINE: Date object
  Source:  JavaScript constant in home.html
  Format:  ISO 8601 with timezone offset (+03:00)
  Default: 2025-12-31T23:59:59+03:00
  Usage:   Countdown timer, "Registration Closed" switch
```

All other card content (heading text, body copy, button label, link target) is static HTML in the template.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Countdown formatter produces correct zero-padded output for all durations

*For any* non-negative duration in milliseconds, `formatCountdown(ms)` SHALL return a string matching the pattern `"DD days HH:MM:SS"` where all four fields are present, DD is zero-padded to at least 2 digits, HH is in the range `00`–`23`, MM is in the range `00`–`59`, and SS is in the range `00`–`59`; and if `ms <= 0`, the function SHALL return `null`.

**Validates: Requirements 3.1, 3.3**

### Property 2: Card is always visible on fresh page load regardless of prior dismissal

*For any* sequence of prior user interactions — including zero, one, or many dismiss actions — a full browser page load SHALL render the Floating_Card in its initial visible state (opacity 1, display not none, aria-hidden not "true"), and NO dismissal state SHALL be written to `localStorage`, `sessionStorage`, cookies, or any other persistent storage mechanism.

**Validates: Requirements 1.6, 5.4**

### Property 3: Card content does not cause horizontal scroll at any standard viewport width

*For any* viewport width in the range [320px, 2560px], the Floating_Card and all its child elements SHALL NOT cause the document body's `scrollWidth` to exceed the viewport's `clientWidth`, i.e. no horizontal overflow is introduced by the card at any standard device width.

**Validates: Requirements 6.4**

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| JavaScript disabled | Card renders as static HTML; countdown shows `<noscript>` fallback; button is a plain `<a href>` that works without JS. |
| `LIGI_DEADLINE` is in the past on page load | `formatCountdown` returns `null`; JS replaces countdown with "Registration Closed" text and hides the Register button, showing the closed-state message instead. |
| Web Animations API not supported (very old browser) | `element.animate` is guarded with a feature check; fallback adds the settled-state CSS class directly, skipping the animation. The button and countdown still appear. |
| `prefers-reduced-motion: reduce` | CSS `@media` rule overrides all animations to `none`; card appears instantly in settled state. |
| User dismisses card, then uses browser back/forward navigation | `display: none` state is not persisted; a full HTTP navigation always re-renders the template, restoring the card. |

---

## Testing Strategy

### Unit tests (example-based)

Target: the `formatCountdown` pure function, extracted into a testable module or testable inline function.

Key examples to cover:
- Exactly 0ms → `null` (Registration Closed)
- Exactly 1 second → `"00 days 00:00:01"`
- Exactly 1 day → `"01 days 00:00:00"`
- 99 days 23 hours 59 minutes 59 seconds → `"99 days 23:59:59"`
- Large value (365 days) → correct DD field

### Property-based tests

Property-based testing is applicable here because `formatCountdown` is a pure function with a large numeric input space where edge cases around zero-padding, field rollover, and boundary conditions are non-obvious.

**PBT library:** [fast-check](https://github.com/dubzzz/fast-check) (JavaScript, MIT licence, no new runtime dependency — used only in the test suite).

**Minimum 100 iterations per property test.**

Each test should be tagged:

```javascript
// Feature: ligi-mashinani-floating-card, Property 1: countdown formatter correctness
```

**Property 1 test outline:**

```javascript
fc.assert(fc.property(
  fc.integer({ min: 1, max: Number.MAX_SAFE_INTEGER }),
  (ms) => {
    const result = formatCountdown(ms);
    expect(result).toMatch(/^\d{2,} days \d{2}:\d{2}:\d{2}$/);
    const [ddPart, timePart] = result.split(' days ');
    const [hh, mm, ss] = timePart.split(':').map(Number);
    expect(hh).toBeGreaterThanOrEqual(0);
    expect(hh).toBeLessThanOrEqual(23);
    expect(mm).toBeGreaterThanOrEqual(0);
    expect(mm).toBeLessThanOrEqual(59);
    expect(ss).toBeGreaterThanOrEqual(0);
    expect(ss).toBeLessThanOrEqual(59);
  }
), { numRuns: 100 });

// And separately: ms <= 0 always returns null
fc.assert(fc.property(
  fc.integer({ min: Number.MIN_SAFE_INTEGER, max: 0 }),
  (ms) => formatCountdown(ms) === null
), { numRuns: 100 });
```

**Property 2 and 3** are browser-environment properties best verified through:
- Property 2: a Playwright/jsdom test that dismisses the card N times then navigates to the page and asserts card visibility + no storage writes.
- Property 3: a Playwright viewport loop test across a range of widths checking `document.body.scrollWidth <= window.innerWidth`.

### Integration / accessibility checks

- Run axe-core against the rendered page to catch ARIA and contrast issues.
- Manual keyboard navigation test: Tab to card → Tab to dismiss → Enter dismisses → Tab to register button → Enter navigates.
- Verify with browser devtools: animation timing, z-index stacking, reduced-motion behaviour.
- Test on Chrome, Firefox, Safari (WebKit) for Web Animations API compatibility.

### No external runtime libraries

The test suite uses fast-check as a dev dependency only. The production template introduces zero new script tags or CDN imports.
