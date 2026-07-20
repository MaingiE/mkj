# Requirements Document

## Introduction

This feature adds a floating card to the MKJ SUPA CUP homepage (`templates/public/home.html`) that invites visitors to register their ward team for the Ligi Mashinani 2026/2029 season. The card uses a physics-based toss animation on page load, settles into a stable position, then reveals an animated "Register Now" button that redirects to the existing Ligi Mashinani registration form (`/ligi/register/`). The feature is purely frontend (HTML, CSS, JavaScript) — no Django model or view changes are required.

## Glossary

- **Floating_Card**: The HTML/CSS/JS card element overlaid on the homepage that displays the Ligi Mashinani registration call-to-action.
- **Toss_Animation**: The physics-inspired CSS/JS animation that causes the Floating_Card to appear to be thrown onto the screen with velocity, rotation, and bounce before settling.
- **Settled_State**: The visual state of the Floating_Card after the Toss_Animation completes — card is at rest, at its final fixed position on screen, with zero rotation (or minimal residual rotation ≤ 2deg), fully readable, and the Register_Button is visible.
- **Countdown_Timer**: A live DD days HH:MM:SS timer embedded in the Floating_Card that counts down to the Ligi Mashinani 2026 registration deadline.
- **Register_Button**: The animated call-to-action button rendered inside the Floating_Card once the card reaches the Settled_State, linking to `/ligi/register/`.
- **Registration_Dashboard**: The existing Ligi Mashinani public team registration page at URL path `/ligi/register/`.
- **Homepage**: The public-facing Django template at `templates/public/home.html`, served by `home_view`.
- **Dismiss_Control**: An "×" close icon on the Floating_Card that allows the user to remove the card from view for the current page view.

---

## Requirements

### Requirement 1: Floating Card Presence on Homepage

**User Story:** As a ward team manager visiting the homepage, I want to see a prominent floating card announcing Ligi Mashinani registration, so that I am immediately aware of the opportunity to register my team.

#### Acceptance Criteria

1. THE Floating_Card SHALL be rendered as an overlay element on the Homepage, positioned above all other page content with a CSS z-index value higher than the highest z-index used by the hero section.
2. WHEN the Homepage `load` event fires, THE Floating_Card SHALL transition from invisible (opacity 0 or off-screen) to fully visible within 500ms of that event.
3. THE Floating_Card SHALL display the text "Ligi Mashinani 2026/2029 Season" as a heading element (h2 or h3) in a font size of at least 20px.
4. THE Floating_Card SHALL display a sub-heading or body text containing the words "Register" and "ward team" (or equivalent Swahili phrasing) to communicate the call-to-action, with a font size of at least 14px.
5. THE Floating_Card SHALL use the project's primary brand colours — one element MUST use the deep blue background (`#0a2f5c`) and at least one accent element MUST use gold (`#E8B91E`) — consistent with the existing homepage design.
6. WHEN the Homepage is loaded or reloaded via a full browser page load, THE Floating_Card SHALL be in its initial visible state regardless of any prior dismissal action in the same or a previous session.
7. WHEN the registration deadline has passed (current time is after the configured deadline), THE Floating_Card SHALL display a "Registration Closed" message in place of the Register_Button, while still showing the heading and Countdown_Timer in its "closed" state.
8. WHEN the user clicks or activates the Register_Button or the "Register Now" link on the Floating_Card, THE browser SHALL navigate to `/ligi/register/`.

---

### Requirement 2: Physics-Based Toss Animation

**User Story:** As a visitor to the homepage, I want to see the registration card animate onto the screen in an engaging, dynamic way, so that it captures my attention without feeling intrusive.

#### Acceptance Criteria

1. WHEN the Homepage `load` event fires and the Floating_Card is not in a dismissed state for the current page view, THE Toss_Animation SHALL start automatically within 100ms of the event without requiring any user interaction.
2. WHEN the Toss_Animation starts, THE Floating_Card SHALL have an initial CSS transform that places its bounding box entirely outside the visible viewport (translate distance ≥ 100vw or 100vh from its resting position) and an initial rotational tilt between -25deg and +25deg.
3. WHILE the Toss_Animation is playing, THE Floating_Card's transform SHALL pass through at least one intermediate position that overshoots the final Settled_State resting coordinates by at least 10px in the primary direction of travel, before returning to the Settled_State; this overshoot SHALL be observable as a discrete keyframe or spring-based intermediate value during the animation.
4. THE Toss_Animation SHALL complete and the Floating_Card SHALL reach its Settled_State within 1500ms of the animation beginning; after that point the Floating_Card SHALL remain stationary unless a user interaction occurs.
5. THE Toss_Animation SHALL be implemented using CSS `@keyframes` / `animation` properties, CSS `transition`, or the Web Animations API (`element.animate()`); it SHALL NOT load or call any external JavaScript animation library (e.g. GSAP, Anime.js, Velocity.js) that is not already bundled in the project.
6. WHEN the `prefers-reduced-motion: reduce` media query matches the user's OS accessibility setting, THE Toss_Animation SHALL NOT play; instead, THE Floating_Card SHALL appear immediately in its Settled_State (transform: none; opacity: 1) without any intermediate frames or transitions.

---

### Requirement 3: Countdown Timer

**User Story:** As a prospective team registrant, I want to see a countdown timer on the card showing how much time remains before the registration deadline, so that I can gauge urgency and act in time.

#### Acceptance Criteria

1. THE Countdown_Timer SHALL display the remaining time to the configured deadline in the format `DD days HH:MM:SS`, where DD is zero-padded to at least 2 digits, HH is zero-padded to 2 digits (00–23), MM is zero-padded to 2 digits (00–59), and SS is zero-padded to 2 digits (00–59); all four fields SHALL always be rendered (e.g. "00 days 00:00:05" when fewer than 6 seconds remain).
2. WHEN the Homepage is open in the browser, THE Countdown_Timer SHALL decrement its displayed SS value by 1 every 1000ms (±50ms tolerance) via a JavaScript interval, without requiring a page refresh.
3. IF the current client time is greater than or equal to the configured deadline timestamp, THEN THE Countdown_Timer element SHALL display only the text "Registration Closed" and SHALL NOT display any numeric time values; this substitution SHALL NOT occur while the current client time is strictly less than the deadline.
4. THE Countdown_Timer target date SHALL be set via a JavaScript constant named `LIGI_DEADLINE` defined in the homepage template, with a default value equivalent to `2025-12-31T23:59:59+03:00` (Africa/Nairobi, UTC+3); changing only the `LIGI_DEADLINE` value SHALL update the timer behavior without requiring any other code changes.
5. IF the browser's JavaScript is disabled or unavailable, THE Floating_Card SHALL render its full static HTML structure — including the "Ligi Mashinani 2026/2029 Season" heading, the Register_Button anchor tag, and a `<noscript>` fallback message in place of the Countdown_Timer — without any JavaScript-dependent content.
6. WHEN the Homepage first renders and JavaScript has not yet executed its first interval tick, THE Countdown_Timer element SHALL display a non-empty placeholder (e.g. "Loading…" or dashes "-- days --:--:--") rather than blank/empty content, so users do not see an empty timer before the first JS tick fires.

---

### Requirement 4: Animated Register Button

**User Story:** As a user who has seen the card settle, I want a clearly animated "Register Now" button, so that I know exactly how to proceed and feel encouraged to click.

#### Acceptance Criteria

1. WHEN the Floating_Card reaches its Settled_State, THE Register_Button SHALL begin a fade-in or slide-in entrance animation lasting between 200ms and 400ms; THE Register_Button SHALL have `pointer-events: auto` and be focusable from the first frame of the animation (i.e. it SHALL NOT use `pointer-events: none` or `visibility: hidden` at any point during the entrance animation).
2. THE Register_Button SHALL display the label "Register Now" in a font size of at least 16px; the computed contrast ratio between the button label text colour and the button background colour SHALL be at least 4.5:1 as defined by WCAG 2.1 Success Criterion 1.4.3.
3. WHEN a user activates the Register_Button by mouse click, touch tap, or keyboard Enter key, THE browser SHALL follow the anchor element's `href="/ligi/register/"` and navigate to that URL; the Register_Button SHALL be implemented as an `<a>` element with an `href` attribute rather than a `<button>` with a JavaScript click handler, so that navigation occurs even with JavaScript disabled.
4. WHILE the Floating_Card is in its Settled_State, THE Register_Button SHALL continuously play a CSS pulsing animation that modulates the button's `box-shadow` or `opacity` on a cycle between 1500ms and 2000ms in duration, with a visible minimum and maximum state that creates an obvious pulsing effect.
5. WHEN a pointer device hovers over the Register_Button, THE Register_Button SHALL transition to a hover state within 200ms that includes either a CSS `scale` transform of at least 1.05 or a change in `background-color` of at least 15% lightness difference from the default state, so that the hover response is perceptible without relying on colour alone.
6. THE Register_Button SHALL have a visible focus indicator when focused via keyboard: a CSS `outline` of at least 2px solid width in a colour with at least 3:1 contrast ratio against the adjacent background, conforming to WCAG 2.1 Success Criterion 2.4.7.

---

### Requirement 5: Dismiss Control

**User Story:** As a user who has read the card and does not wish to register now, I want to close the card so that it does not obstruct my browsing of the rest of the homepage.

#### Acceptance Criteria

1. THE Floating_Card SHALL include a Dismiss_Control button element positioned in the top-right corner of the card, with non-zero rendered dimensions (width ≥ 24px, height ≥ 24px), opacity > 0, and a colour contrast ratio of at least 3:1 between its icon/text colour and the card background colour.
2. WHEN a user activates the Dismiss_Control, THE Floating_Card SHALL begin a CSS fade-out transition (opacity from 1 to 0) with a duration of exactly 300ms.
3. WHEN the fade-out transition completes (300ms after Dismiss_Control activation), THE Floating_Card element SHALL have `display: none` or `visibility: hidden` applied so it no longer occupies layout space or receives pointer/keyboard events; its `aria-hidden` attribute SHALL be set to `"true"`.
4. WHEN a full browser page load occurs (new HTTP navigation or hard reload), THE Floating_Card SHALL be rendered in its initial visible state, regardless of whether it was dismissed during the previous page view; dismissal SHALL NOT be persisted across page loads via `localStorage`, cookies, or any other storage mechanism.
5. THE Dismiss_Control SHALL be reachable and operable via keyboard Tab navigation; pressing Enter or Space when the Dismiss_Control has focus SHALL activate the dismiss behavior described in criteria 2–3.
6. THE Dismiss_Control element SHALL have an `aria-label` attribute with the exact value `"Close registration card"` for screen-reader identification.

---

### Requirement 6: Responsive Layout

**User Story:** As a visitor on a mobile device, I want the floating card to display correctly on small screens, so that it is readable and usable on any device.

#### Acceptance Criteria

1. THE Floating_Card SHALL have a CSS `max-width` of 420px on viewports ≥ 480px wide; on viewports < 480px wide, THE Floating_Card SHALL have `width: calc(100% - 2rem)` (i.e. full viewport width minus 1rem margin on each side) so that it fills available horizontal space without overflow.
2. WHEN the viewport width is less than 480px, THE Floating_Card SHALL be positioned using `position: fixed; bottom: 1rem` anchored to the bottom of the viewport; on viewports ≥ 480px, THE Floating_Card SHALL default to a centered or right-offset fixed position that does not cover the primary hero headline.
3. THE Floating_Card SHALL render all text (heading, body copy, Countdown_Timer digits, Register_Button label) with a minimum computed font size of 14px on a 320px-wide viewport, and the Register_Button SHALL have a minimum touch target area of 44×44px as recommended by WCAG 2.5.5.
4. THE Floating_Card SHALL use `overflow: hidden` or equivalent CSS to prevent its content from extending beyond its own boundaries; no child element SHALL cause the document body to scroll horizontally on any viewport width from 320px to 2560px.
