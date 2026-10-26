# Amazon Gallery and Premium A+ planning

Select Gallery, A+, or both from the actual instruction; there is no automatic A+-only default. If neither the instruction nor saved context identifies scope, clarify it once. Gallery defaults to 9 images; Premium A+ keeps its normal 13 within 9–15. Both normally means 9+13. Explicit counts override these defaults. Product initialization need not wait for this choice; before set planning/generation, ask once if the channel remains unresolved and save the answer. The [desktop A+ structure](a-plus-module-layout.md) applies only to selected A+ work; Gallery keeps its own canvas/content rules.

## Explicit expanded mode

Activate `--mode expanded` for an explicit 30–40-image or large exploration request in the selected channel(s). The fallback is 36 per selected channel, with a 40-per-channel limit; never choose both channels just because expanded mode was requested. Two ordinary sets of 15 are still standard mode. Explicit quantities override the fallback. A grouped A+ draft can retain its structure/canvas and grow via `add_a_plus_image.py --activate-expanded` after the user's request.

## Content coverage

Separate-file delivery can contain selling-point copy, icons, comparisons, detailed internal panels and verified steps. Main-image restrictions and explicit no-copy instructions apply only where relevant. Plan the message and needed source per image before its pose/layout. Missing evidence is a gap, not permission to substitute an unrelated image under the same topic label. Compare the final set against the user's content brief, not only counts and filenames.

## Gallery

The department default is nine separate images, with the following responsibilities. This is a production framework, not a statement about listing upload capacity. Explicit counts, scopes and current instructions override it; saved queues are not migrated on resume.

| Positions | Responsibility | Fixed content / AI freedom |
|---|---|---|
| 01–02 | White product displays | Accurate sold object, white background, no promotional copy. Default to upright front/reverse views in the evidenced assembled form; an explicit requested pose overrides this default. Upright applies only to this opening pair. |
| 03–05 | Selling-point explanation | Cover the required selling points and selection/use information with clear priorities. AI chooses overall/detail relationships, supported states, comparisons, insets, graphics and parameter combinations. No compulsory material/hardware/mechanism assignment by position. |
| 06 | Flexible product display | Show the required styles, parameters, wearing details or their combination. AI freely chooses flat-lay, upright samples, staggered/grouped or wearing combinations, scale, views and graphic relationships from actual available information; do not inherit the opening pair's upright pose. |
| 07–09 | Distinct lifestyle displays | No added promotional lettering. AI chooses relevant people, activities, wardrobe, settings and framing; keep the product readable and naturally worn/used. |

### Opening pair: inspect first, inherit identity rather than pose

For a new full Gallery set using this framework, execute its existing first two white-display child IDs through the single-image skill first, then inspect them together against the original evidence, show both actual outputs to the user, and stop for explicit user approval before any remaining Gallery image is generated. They remain two of the selected nine outputs, not a separate project or two additional pilots. Explicit single/pilot scope and supplied ordering retain their scope. In this Gallery opening workflow, the pair must depict the physical product upright in front/reverse views; correct a flat or spread-open result before presenting it. A+ execution is unchanged.

Upright means the physical product stands in space, not merely a portrait canvas or a vertically arranged flat product. For a band, retain the evidenced assembled loop and show front/reverse relationships; do not open connections, invent a stand or infer unseen structure to achieve the pose. AI chooses angle, camera height and perspective that reveal the required features. Save this pose only in the opening children's `quality_contract.layout.composition`, `creative_brief` and, when required, local `image_intent.must_show`. Explicit user instructions can replace it. Do not put upright/front-view/white-background composition into shared identity locks or copy it into later children.

Joint inspection checks the required upright pose and front/reverse coverage, compares each view against originals, and reconciles component ownership, inside/outside surfaces, connections and routing between the two. Agreement between two generated images alone does not establish correctness. Distinguish a rendering defect (correct the candidate), a mistaken product interpretation (apply an evidence-backed product-state revision), and a genuine evidence gap (keep it unresolved). Record concrete observations in existing QA, declaring the other opening image as a comparison when inspected together. A self-check remains `PENDING_REVIEW`, never fabricated human acceptance.

Load and follow the [single-image skill](../../product-single-image-generator/SKILL.md), rather than merely borrowing its name or sending the whole set brief to the image tool. Prepare only the opening IDs, attach their selected original evidence, generate one image per call and perform the single-image checks/corrections. Render both current images for user inspection with a concise front/reverse label and unresolved issues. Save candidates and QA, then yield to the user; do not generate image 03 or the other Gallery images in the same turn before approval. Self-checks, internal plan `--approve`, silence, or a correction request do not constitute user approval. One explicit user message may approve both images when it clearly covers the displayed pair; partial approval leaves the other pending.

New full Gallery plans with a remainder store `gallery_opening_review: {version: 1, image_ids: [<front-id>, <reverse-id>]}` in the existing plan. The runtime derives approval from the two current candidate records: both must be `ACCEPTED` with the real user's decision reference, matching candidate bytes, contract and valid QA. Use the existing per-image `record ... --decision ACCEPTED --report ... --human-reviewer ... --decision-reference ...` only after that actual message. `HUMAN_STRUCTURE_REVIEW_PASSED` alone does not release the gate. `next-generation` allows producing both opening images while the first awaits review, then returns `WAIT_FOR_GALLERY_OPENING_APPROVAL`; direct prepare, generation-packet, contract-materialization and single-image preflight paths also refuse the remainder. A+ tasks retain their own policy. Saved plans without this marker keep their prior execution contract; adopt this flow via an explicit plan revision or new set, never by rewriting pinned history.

After approval, carry only current supported facts/relations, relevant original evidence, required content, unresolved dependencies and eligible candidate pointers into later tasks. Generated images remain appearance references within reviewed visible scope, never evidence for hidden structure, dimensions or variants. Use existing reference-eligibility and immutable-snapshot rules. Changing, rejecting or retrying an opening image invalidates approval for that image; show the revised current pair and wait again. Do not transfer approval from old candidate bytes to a replacement.

If that inspection changes facts or a later design/reference, revise only affected tasks under the existing state/snapshot rules before execution; never silently inject new content into approved contracts. The gate is derived from existing candidate/QA/human-decision records, without a separate approval database. The pair establishes a product baseline, not a design template: later selling-point, parameter, variant and lifestyle images keep their own task-specific poses/compositions and visual checks.

### Variant display: fixed products and information, free design

For the flexible product-display child, fix which real styles/colours/patterns are required, their product identity and differences, accurate parameters and the buyer's selection question. Leave pose, sample arrangement, framing, perspective, props and graphic relationships to AI unless currently specified. Flat-lay, upright multi-sample arrangements, staggered/radial/grouped compositions, wearing comparisons and product-plus-parameter combinations are possible treatments, not a menu or quota. Single-product and parameter-only assignments do not require inventing a range.

Choose a treatment by what needs to be understood: pattern coverage, colour comparison, wearing differences or parameter correspondence. AI may explore alternative arrangements internally and search for targeted layout/light/space inspiration when useful, then select a design within the shared visual system. No fixed number of alternatives, additional generated samples, external references or user layout approval is required. Search/style references contribute only their declared visual elements; preserve the actual product's structure, texture, hardware, colours and pattern placement from original evidence. Simulated colour concepts cannot silently become actual sale variants.

Save mandatory content in `image_intent.must_show`/fact dependencies and the chosen arrangement in `creative_brief` with observable success criteria. A chosen layout is a revisable decision for this child, not a new identity fact or a compulsory layout for its neighbours. Inspect (1) whether actual products/variants remain faithful, (2) whether every required choice and parameter is present and attributable, and (3) whether the arrangement makes the relevant differences legible instead of obscuring them. Style variety is allowed; changing the product or losing selection information is not. Absence of the opening pair's pose is not a failure for this task.

### Initialization, design and current state

Keep the existing project initialization → set planning → single-image generation sequence. Initialization establishes product evidence/current facts and requirements; its empty design fields are drafts for AI to complete, not a request that the user supply finished examples. Before approving/generating, AI fills the existing `image_intent`, `creative_brief`, `visual_system` and `execution_policy` from the current state. No parallel context document, selling-point database or approval form is needed.

Distinguish constraints from creative freedom. In intake `must_show` (then `image_intent.must_show`), retain observable required content and any explicitly current presentation requirement, such as a bending demonstration or a comparable multi-colour arrangement. Supported facts carry their IDs; exact copy stays in copy fields. AI chooses unspecified composition, pose, scene, panels and visual devices within shared style boundaries. Put its chosen expression in `creative_brief.visual_device`, hierarchy/graphics and observable `success_criteria`; these are design decisions, not newly verified product facts. Downstream receives this image's resolved state and selected original evidence, not the intake transcript, rejected ideas or all sixteen uploads. File handoff does not erase actual chat history.

Before generation, compare every mandatory item in the current brief with its assigned child image(s), including parameters/compatibility and required demonstration methods. Reuse the existing ledger and image records. Several related requirements may share an image; a requirement may span images with distinct contributions. Three selling-point images do not mean only three selling points. Slot 06 is flexible, not the only place parameters may appear. Rebalance related content within the selected count rather than dropping a requirement or silently converting a required demonstration into a title. If the requested coverage cannot fit legibly, preserve the unresolved requirement and explain the concrete conflict; do not expand the set without scope authorization.

### Product evidence versus optional design references

Judge evidence for the assigned content, not photo count, variety or the existence of a finished layout sample. A package of product pictures and a requirement document is a normal input. Missing flat-lay, parameter-layout, moodboard or wearing examples does not itself justify `NEEDS_EVIDENCE`: AI designs those relationships. Both ADVANCED and AI_ASSISTED may choose unspecified design details; the absence of a finished reference alone does not force a mode change.

- With evidenced variants, AI may arrange comparable samples, worn views or a combined product/parameter presentation. Without multiple verified variants, do not invent colours/patterns to fill a range task.
- With supported dimensions/fit specifications and adequate product identity, AI may create measurement/compatibility graphics without a finished parameter example. Do not estimate specifications from photographs.
- With limited viewpoints, choose a composition that exposes evidenced features. A new arrangement does not require a matching sample photograph, but unseen geometry, internal layers and operating states cannot be fabricated.
- For a proposed treatment that needs unknown structure or facts, first choose another supported treatment that still fulfils the same task. Only genuinely missing mandatory facts block the affected task. Do not replace a required range, parameter or use task with an unrelated beauty image.

At final review, compare actual pixels with required content and the chosen brief: visible selling-point treatment, accurate variants/patterns, clear parameter-to-product correspondence and distinct lifestyles. Existing `content_coverage`, `module_role_fit` and `design_quality` record observations. Count/record validation cannot establish visual success. Feedback updates only affected current state and tasks; historical candidates remain archived.

For explicit seven-image or larger requests, AI redistributes these responsibilities and preserves mandatory coverage rather than truncating the nine-image draft. Do not impose the nine-image split on an imported explicit brief. Extra files need distinct tasks, not repeated closing images.

## Premium A+

For this department's A+ use the [page skeleton and seven responsibilities](a-plus-module-layout.md#page-skeleton-and-seven-responsibilities), normally 13 separate 1464 × 600 images. Plan the upper product explanation/use/selection section, followed by lifestyle; allocate extra slides inside those responsibilities. Product introduction, core material/benefit, structure/craft, function/use, range, size/compatibility and lifestyle provide coverage; related responsibilities may share a group. Care belongs within function/use when relevant and supported. Adapt the initializer's legacy order before approving a new draft. The generic conceptual sequence below is an alternative when explicitly selected, not an automatic substitute for the design brief. Adapt image count between 9 and 15 to actual coverage; page groups and image count are independent.

1. Brand/product hero.
2. Material story.
3. Signature detail.
4. Craftsmanship or hardware.
5. Comfort or use experience.
6. Installation or adjustment.
7. Compatibility or size guidance.
8. Lifestyle integration.
9. Range, gift, or closing brand moment.

## Set rules

- One clear primary sales task per image; internally related details/comparisons/steps may support it.
- No more than two consecutive modules with effectively the same view.
- Use at least four meaningful viewpoints when product evidence supports them.
- Put high-priority supported selling points early.
- Follow information-heavy modules with quieter visual modules.
- Lifestyle images remain product-led and keep the product readable.
- Keep main-image rules separate from secondary-image design.
- Do not combine modules into a contact sheet, nine-grid, or crop source.
