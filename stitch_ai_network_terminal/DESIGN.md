# Design System Strategy: The Intelligent Monolith

## 1. Overview & Creative North Star
The "Intelligent Monolith" is the creative North Star for this design system. It moves away from the "toy-like" appearance of common SaaS dashboards and instead draws inspiration from high-end editorial layouts and brutalist architectural precision. 

The system is designed to feel like a high-performance instrument—authoritative, dense, and hyper-functional. We break the "template" look by utilizing extreme typographic contrast (oversized editorial headers against minute technical data) and a "chromatic depth" approach. Instead of using boxes to contain information, we use light and tonal shifts to define the boundaries of the digital space.

## 2. Colors & Surface Logic
The palette is rooted in a "Deep Space" philosophy: absolute blacks and charcoals provide the foundation, while the `primary` (Electric Indigo) acts as the high-energy signal in a low-noise environment.

### The "No-Line" Rule
Designers are strictly prohibited from using 1px solid borders to section off major UI areas. Structural definition is achieved through:
- **Tonal Shifts:** Transitioning from `surface` (#131313) to `surface-container-low` (#1B1B1C).
- **Negative Space:** Using the spacing scale to create clear mental models of containment.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. 
- **The Bedrock:** `surface_container_lowest` (#0E0E0E) for the raw terminal output.
- **The Worksurface:** `surface` (#131313) for the primary application background.
- **The Tooling:** `surface_container` (#202020) for panels and sidebars.
- **The Active Focus:** `surface_container_high` (#2A2A2A) for active chat bubbles or focused inputs.

### The "Glass & Gradient" Rule
To distinguish the AI layers from the terminal's raw logic, use **Glassmorphism**. Floating AI panes must use `surface_variant` at 60% opacity with a `20px` backdrop blur. 
**Signature Texture:** For primary actions, use a subtle linear gradient from `primary` (#C3C0FF) to `primary_container` (#4F46E5) at a 135-degree angle. This adds "soul" and depth to the precise terminal environment.

## 3. Typography
The system uses a dual-font strategy to separate **Output** from **Interaction**.

*   **Display & Headlines (Space Grotesk):** This is our "Editorial" voice. It is used for high-level navigation, system status headers, and AI persona titles. It should feel wide, modern, and high-tech.
*   **Interface & Reading (Inter):** Used for AI chat responses and UI labels. It provides the "human" bridge to the machine.
*   **The Terminal (JetBrains Mono/Fira Code - *External*):** While not in the core JSON, all code and raw network data must be rendered in a high-quality monospace font to maintain the "Power User" aesthetic.

**Hierarchy Note:** Use `display-lg` sparingly for system states (e.g., "SYSTEM: READY") to create a sense of scale. Contrast this with `label-sm` for technical metadata to emphasize information density.

## 4. Elevation & Depth
In this system, elevation is not about "distance from the screen" but "density of the layer."

*   **The Layering Principle:** Place a `surface_container_lowest` card inside a `surface_container_low` section to create a "sunken" terminal well. This creates focus without visual clutter.
*   **Ambient Shadows:** For floating AI modals, use an extra-diffused shadow: `0 24px 48px -12px rgba(15, 0, 105, 0.4)`. The indigo tint in the shadow makes the AI feel like it is emitting light rather than just casting a shadow.
*   **The Ghost Border:** If high-density data requires visual separation (like table rows), use the `outline_variant` token at **15% opacity**. Never use 100% opaque lines.
*   **The AI Glow:** AI-generated content should have a soft, `secondary_container` inner-glow (blur: 40px) to differentiate it from the "cold" terminal data.

## 5. Components

### Buttons
*   **Primary:** Gradient fill (Primary to Primary-Container), `label-md` uppercase, `0.25rem` (sm) corner radius.
*   **Secondary:** Ghost style. `outline` border at 30% opacity, white text. No background fill.
*   **Tertiary:** Monochromatic light gray text, no border. On-hover, background shifts to `surface_container_high`.

### Input Fields
*   **Terminal Input:** No background, no border. Indicated only by a `primary` color cursor and a `primary` left-accent line (2px).
*   **AI Chat Input:** Glassmorphic (`surface_variant` @ 40%), `blur: 10px`, rounded-xl (`0.75rem`).

### Chips
*   **Action Chips:** `surface_container_highest` background with `on_surface_variant` text. Use `full` rounding for a pill shape.
*   **AI Suggestion Chips:** Subtle indigo border (`primary` @ 30%) with a soft glow on hover.

### Cards & Lists
*   **The "No-Divider" Rule:** Use `surface_container_low` and `surface_container_high` to alternate list items or use 16px of vertical white space. Dividers are considered "ink-waste" in this system.

### New Component: The "Breadcrumb Trace"
For network paths, use `label-sm` text with `primary` color chevrons. This emphasizes the "Network Terminal" identity of the tool.

## 6. Do's and Don'ts

### Do
*   **Do** embrace asymmetry. A sidebar can be significantly "heavier" than the main content area if it increases utility.
*   **Do** use `primary_fixed_dim` for text that needs to be "Active" but not "Urgent."
*   **Do** use 85% opacity for secondary text to create a natural hierarchy without changing colors.

### Don't
*   **Don't** use standard "Success Green." Use the `secondary` slate-blue tones for success and `error` (#FFB4AB) only for critical system failures.
*   **Don't** use rounded corners larger than `0.75rem` (xl) for functional elements; we want the system to feel sharp and precise, not "bubbly."
*   **Don't** use pure white (#FFFFFF) for body text. Use `on_surface` (#E5E2E1) to reduce eye strain in the dark terminal environment.