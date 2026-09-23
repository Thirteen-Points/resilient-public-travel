# Frontend references and attribution

## Agent avatar

`src/lib/bloub/` is an adaptation of the bot engine from
[jeremy-prt/bloub](https://github.com/jeremy-prt/bloub) by Jérémy Perret,
licensed MIT:

> Copyright (c) 2026 Jérémy Perret
>
> Permission is hereby granted, free of charge, to any person obtaining a
> copy of this software and associated documentation files (the "Software"),
> to deal in the Software without restriction, including without limitation
> the rights to use, copy, modify, merge, publish, distribute, sublicense,
> and/or sell copies of the Software, and to permit persons to whom the
> Software is furnished to do so, subject to the following conditions: The
> above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED
> "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
> NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
> PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
> HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
> ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
> CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Carried over from `src/bot/` of the original: the clock-free `sample(t)`
engine with time-stamped setters and mid-fade pose freezing (`engine.ts`),
the sphere-projected eyes with the fitted `REST_GAZE` orientation
(`face.ts`), the pre-drawn deterministic blink calendar and `loopNoise`
liveliness (`face.ts`, `math.ts`), the equal-topology radial profiles and
Catmull-Rom path builders (`shape.ts`), and the measured triangle profile,
thinking three-dot positions and `play`-state face constants (`profiles.ts`,
`engine.ts`). The body colours are the bloub palette entries `vert`
(#3ecf8e) and `rouge` (#e8483f). Deviations from the original: the catalogue
is cut to the three states this app needs (idle, thinking, and `play`'s still
triangle without its swoosh bouquet), the React/SVG mask rendering replaces
the Vue component, colours morph through `mixHex` alongside shape changes,
and a frozen-frame mode renders stills for reduced-motion users. The `eyes`
remain holes cut in the body, as in the original.

Bloub recreates an x.ai avatar as a reverse-engineering exercise; its MIT
license covers its code, not the xAI design. Neither bloub nor this project
implies an affiliation with xAI.

## Animation packages

- GSAP and @gsap/react: https://gsap.com/ — licenses distributed with packages.
- BorderBeam: https://github.com/Jakubantalik/Libraries.dev/tree/main/packages/border-beam
  — actual React `border-beam` package, with restrained monochrome focus treatment.

## Presentation metadata

- MTR route colours: https://www.mtr.com.hk/ch/customer/services/system_map.html
- Citybus yellow brand: https://www.citybus.com.hk/en/uploadedPressRelease/20212_20230531_ENG.pdf
- KMB red: https://www.kmb.hk/milestones.html
- Operator assignments: project `docs/plan/08-data-appendix.md` (seed corridor;
  presentation metadata only, not live operator verification).
- Known 2026 HK public holidays: https://www.gov.hk/en/about/abouthk/holiday/2026.htm
  (calendar marks September/October only).

Unknown route colours are deterministic presentation choices, labelled as assigned.
Geometry, travel times and incidents retain their existing seed provenance.
