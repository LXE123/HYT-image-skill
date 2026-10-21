# Creative planning and visual direction

Material/structure accuracy and commercial visual design are separate outcomes. Accurate material is a valuable baseline, not proof of a strong composition. More files, glow, props or icons do not automatically improve design. Plan the selling idea and its visual expression before describing camera/light/boxes.

Use [autonomous-design.md](autonomous-design.md) for input-led decisions and self-directed reference research. The executable [design library](design-library.md) supplies optional layout/style starting points. Adaptive mode can use an actual free composition without selecting a catalog style; evidence and explicit requirements retain priority.

For integrating visual languages into the product and a complete set, read [product-led style integration](product-led-style-integration.md). It covers input-led decisions, role-dependent expression, atmosphere/cohesion and scoped feedback without embedded sample imagery or automatically loaded historical experiments.

## Set-level direction

Choose a direction from brand/positioning, audience, use context and strongest supported differentiator. Material is one input, not a mandatory style preset: woven products can use energetic sport, editorial fashion, technical detail or quiet daily-life language when the actual brief supports it. Do not assign every nylon product pale-blue soft utility by habit.

Store one shared system in `visual_system`: mood, palette, typography/hierarchy, background families, lighting, icons, props, casting/wardrobe, retouching and forbidden cues. Use a limited, coherent vocabulary; the existing defaults are starting suggestions rather than quotas. Product colours/materials remain faithful across different settings.

### Shared boundaries, varied images

Choose one set-level background and lighting baseline from the current product/brand and the direction already accepted in this task. State the dominant background lightness (light, midtone or dark), colour family, warm–cool balance, contrast/shadow range and type family. Keep these decisions in existing `visual_system.background`, `palette`, `lighting`, `typography` and `forbidden_cues`; no separate style record or compulsory new schema is needed. Generic “premium/cohesive” wording alone leaves these decisions unresolved.

Per-image `design_adjustments`, catalog treatments, creative briefs and selected style references refine within this shared range. They cannot independently switch the dominant background from light to dark, reverse the colour grade or replace the type family. Composition, camera, background material, scene, scale, density and local highlight direction may vary. Bright and dark details can coexist inside the chosen range; product colours, skin and evidenced materials keep their true appearance. Required white Gallery main images retain their own constraints.

When feedback asks for unified backgrounds, keep the task's agreed dominant range rather than inventing alternating dark/light pages for variety. Deliberate contrast needs an explicit set-level requirement; an individual brief cannot create its own exception. If the shared direction itself changes, revise it at set level and check dependent images under the existing revision rules.

For a task that has selected a light warm-neutral direction, a useful example is:

```json
{
  "background": "Dominantly light warm neutrals; cream, pale stone and bright natural settings; deep tones remain local accents, not full dark backgrounds",
  "palette": ["cream white", "warm pale stone", "muted natural accents"],
  "lighting": "Soft warm-neutral light, low-to-medium contrast and open shadows; local direction may change without a cool grade or crushed blacks",
  "typography": "One sans-serif family and consistent heading/body hierarchy; size, position and line breaks adapt to the task",
  "forbidden_cues": ["unplanned dark full background", "cold blue overall grade", "heavy black shadows"]
}
```

This illustrates a selected direction, not a preset for every product. Describe a relative visual range; exact hex matches or fixed background photographs are unnecessary unless the user requires them. Include the same concise shared rules in each actual generation input. For web execution, carry them in every current-image instruction, not only the initial plan. A selected real style reference may help when available, with its limited style role; do not make a new moodboard, reference image or approval stage mandatory.

Plan a deliberate set rhythm: opening recognition/appeal, feature proof, material/construction, evidenced use, selection guidance, and emotional/use context as relevant. Vary scale (full product/detail/full lifestyle), density (explainer/quiet scene), focal position and spatial depth. Cohesion means a shared language, not the same left-empty/right-product photograph repeated. Main-image clarity on white remains valid and should not receive decorative effects to satisfy this guidance.

A structure-only competitor reference supplies its page/content organization only. A separate authorized style reference may guide visual language, with its limited source role. Neither can establish the actual product's geometry, texture, mechanism or claims.

## Feature coverage and freedom of expression

Use the initial product intake's supported facts and selling points. Assign the important requested features, benefits and selection questions to existing image tasks before filling the set with scenes. Preserve explicitly requested lifestyle tasks; do not use them to replace deferred or under-explained feature modules. Judge information coverage, not the number of attractive files or language/size variants. Do not prescribe a feature/lifestyle quota or require one image per fact.

For each image, choose which points have a natural, evidence-grounded visual expression and which remain only in copy. Both can coexist in one composition. A clear weave close-up can show texture; it does not prove breathability, skin compatibility or hours of comfort. A static clasp can show its construction, not holding strength or an unobserved release motion. If visualization would be forced or misleading, use confirmed text with a suitable product/context image; do not invent an effect just to connect the words to the scene. Pure atmosphere may serve an assigned emotional task without illustrating a benefit.

Record the decision in the existing `creative_brief` (visual device, graphic treatment, hierarchy and success criteria), not another expression registry. Keep copy-only points out of visual `must_show`/fact dependencies. Exact copy supplies lettering; it is not a command to stage its claims. Supplied wording stays exact; writing new copy needs authorization. Missing evidence cannot be bypassed by using text.

Constrain product identity, evidence, required information, exact copy, scope and the A+ canvas of 1464×600. Let AI choose composition, suitable scenes, visual devices and information density; lighting and typography vary within the selected shared range. Integrated image/text generation or separate typesetting may be chosen for accurate, legible output; neither is a mandatory extra stage. A separate text pass must preserve the product image and receive the final copy without turning it into new scene instructions.

## One image's creative brief

When showing analysis of a requirement sheet, include the mapping from each module's job to its design language, not just a role such as material/lifestyle. Explain the intended visual evidence, the role of copy/graphics, and what would fail to answer the task. The single-image resolver supplies functional principles; AI then proposes the actual per-image relationships from the filtered brief. These proposals are not facts extracted from old reference styles. Deferred tasks still have responsibilities and a possible explanatory language, but no invented dimensions or operating states.

New drafts have `creative_policy_version: 1` and a `creative_brief` in each image spec. Fill it before approval. The fields answer different questions from the physical camera/pose/boxes in `quality_contract.layout`; do not duplicate the whole technical contract or shared style.

| Field | Decision |
|---|---|
| `layout_id` / `story_stage` | Use adaptive for a free non-main composition, or a compatible catalog starting point; mark the image's actual task stage |
| `visual_concept` | What should this particular image make the buyer notice/understand? |
| `visual_device` | What visual relationship expresses that idea: recognizable action, scale contrast, actual material fold, supported detail inset, comparison, verified step sequence, etc.? |
| `information_hierarchy` | Ordered primary focus, secondary proof, and optional labels/support; the viewer's reading path |
| `graphic_treatment` | Copy/graphic/effect treatment, or an explicit photographic-only choice justified by the task |
| `set_role` | What this image adds and how it differs from its neighbours |
| `success_criteria` | Visible criteria for design review, specific enough to judge the output |

In adaptive mode, optional `design_adjustments` refines named visual dimensions for this image within the shared boundaries (`palette`, `lighting`, `typography`, `background`, `graphics`). Optional `reference_influences` records `{source_id, element, strength, reason}` using this image's registered `style_source_ids`; `strength` is `low`, `medium` or `high`, a planning intent rather than a calibrated model control. Neither field requires external references or wholesale redesign.

Keep the brief compact, normally a few short sentences and short ordered lists. “Premium”, “clean”, “photorealistic” or a colour palette alone do not answer these questions.

For material proof, a usable concept might connect a readable actual surface detail with a product/context cue and an approved benefit label; decide how the eye moves between them. For a lifestyle task, describe the meaningful activity/person/environment and the role of the worn product, rather than merely a wrist in bokeh. For a feature explainer, choose the supported visual proof and its hierarchy before adding effects. Comparisons, icons, internal panels and copy are optional tools, not requirements for every image.

Graphic effects may explain an evidenced fact but never become its evidence. Do not invent magnetic fields, airflow, waterproofness, invisible layers, component separation or operating directions. Keep illustrative overlays visibly separate from physical product structure. If a desired idea requires missing evidence, obtain it or explicitly replan that task rather than silently replacing it with another texture macro.

## Pilot before extending a direction

Follow the [internal pilot rule](autonomous-design.md#内部检查后继续授权任务): select 1–3 existing child tasks according to risk, inspect them, then continue the authorized set while human review is pending. A white main image alone does not test varied A+ expression. A pilot-only request stops at its own scope. Preserve failed candidates and revise them under the existing history rules.

## Design quality review

New creative briefs require `design_quality` in visual QA, alongside product accuracy and `content_coverage`. Inspect the rendered image against its own brief:

- A deliberate focal point and readable hierarchy/reading path.
- Composition, scale, depth and negative space used for the assigned job, not automatic empty space.
- Actual copy/icons/panels/effects integrated and legible when assigned, without decorative clutter or obscuring the product.
- Lifestyle person/action/environment and emotional relevance when assigned, with a readable product.
- A contribution distinct from adjacent images within the shared visual system.
- Set continuity: compare actual images side by side for dominant background lightness/colour family, warm–cool grade, contrast/shadow depth and type family. A broad jump from the selected range fails `design_quality` even when the image looks good alone. Different scenes or surfaces within the range are allowed; a dark product does not make a light background inconsistent. Correct the affected background/light/grade/type while preserving product truth and successful composition where possible. Record concrete observations in the existing check; scripts cannot prove visual consistency.
- Required product information is actually understandable through the assigned picture and/or exact copy. A texture photo with no required explanation, or a different person/place repeating the same message, does not add feature coverage. Respect copy-only treatment; lack of a physical visualization is not itself a failure.
- Product-led integration and atmosphere: the intended lighting, setting, depth or graphic relationship is visible and coherent; decorative effects do not compete with the selling idea, distort the product or make explanation/selection harder. Review actual composition and clutter, not only selected style/layout IDs.

Record concrete observations and failures; a material/structure pass cannot stand in for this review. Scripts verify that the decisions/checks exist, not whether an image is beautiful or persuasive. Judge the pilot and final set visually at intended display size. The new workflow cannot prove improved image quality until new candidates have actually been generated and reviewed.
