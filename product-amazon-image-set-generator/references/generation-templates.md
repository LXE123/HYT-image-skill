# Concrete Amazon generation templates

Read when filling a set plan. The versioned machine-readable catalog is [generation-templates.json](../assets/generation-templates.json). `init_visual_set.py` snapshots it once in the set and records only a template ID/revision in each plan row; normalized product/copy boxes live in the separate module spec. These remain drafts until evidence and pose/layout details are filled. Coordinates are fractions of that module's own canvas, not an Amazon platform specification. Confirm current marketplace size/rule requirements separately when preparing an actual listing.

## Default sequence and composition

Choose Gallery, A+, or both from the user's instruction/context; ask once before set planning/generation if unresolved. Gallery defaults to nine images using [its 2+3+1+3 framework](amazon-planning.md#gallery). Premium A+ retains its normal 13 within 9–15 and its [desktop structure](a-plus-module-layout.md) with 1464 × 600 outputs. Explicit counts/channels and saved plans take precedence.

| Gallery seed | Template | Task |
|---|---|---|
| 01–02 | `main_product` | Upright front/reverse white displays by default; explicit requested pose takes precedence. No promotional lettering; this pose is local to the opening pair. |
| 03–05 | `product_overview` initially | Three selling-point responsibilities; AI selects an appropriate template after deciding actual required content and expression. |
| 06 | `product_overview` initially | Product display: style arrangement, verified parameters, wearing detail or a combination. Select `range_story` or `size_fit` only if that is the actual task. |
| 07–09 | `lifestyle_simple` | Three distinct relevant people/activity/settings without promotional copy. |

The seed deliberately does not require hardware, a mechanism, multiple variants or dimensions merely because of a position. Complete each draft from the current brief; switch template and relevant quality fields to match the actual design before approval. A neutral template never waives visible-hardware or motion checks. Keep mandatory content in `image_intent.must_show` and selected expression/success criteria in `creative_brief`; follow the Gallery guide for coverage and optional references. A missing layout/pose example is not a product-evidence gap. First inspect the opening pair against originals under the [Gallery handoff](amazon-planning.md#opening-pair-inspect-first-inherit-identity-rather-than-pose); later variant displays may be flat, upright or otherwise arranged from their own brief. Do not copy main-image pose rules into the shared template catalog, product identity or later children. Explicit non-nine counts need AI redistribution rather than accepting a truncated seed as a finished plan.

Generic Premium A+ templates map to overview, material, static signature, static construction, simple lifestyle, mechanism, size, simple lifestyle, range. The selected [department A+ profile](a-plus-module-layout.md) selects its own templates per image and uses exact 1464 × 600 output instead. Choose composition by content task. Selling-point images may use approved copy, icons, comparisons and related detail regions; verified use images may have several steps; full lifestyles need recognizable people/actions/environments. Separate-file delivery is not a blanket ban on copy or internal panels. Do not force all images into a left-copy/right-product layout. Redesign the scene for the wide canvas; do not stretch a square image or reuse a crop that hides the product. Aspect ratios remain user-adjustable.

Use `layout_id: adaptive` and a task-specific composition by default. Read [design-library.md](design-library.md) only when choosing a catalog starting point. Templates retain evidence/anatomy/operation constraints rather than prescribing a universal visual layout.

For each module select `template_id` and `template_revision` in its plan row. The resolver loads the exact pinned object as `generation_template` in memory; do not copy its text into every file. Fill the spec's `quality_contract.layout.composition` with camera, product size/placement and text region; set the neutral draft boxes from that composition rather than inheriting a left-copy/right-product split. Fill all visible-hardware state checks, and human pose/ownership/contact/occlusion fields when anyone appears, including hands-only macro shots. A hardware template with fingers must have `human.present: true` even though the template itself does not require a person.

Use the [single-image quality schema](../../product-single-image-generator/references/visual-quality.md). An example there illustrates fields, not the truth of this user's strap. No default template establishes that a clasp is magnetic, hinged, sliding, removable, or opened by lifting.

## Generation and validation

1. Validate and approve the completed plan; missing pose, state evidence, or verified operating claims block approval.
2. Call the runtime's `prepare` to materialize the current image's reference envelope. It resolves its pinned template, selected lock facts, copy and quality fields into a focused prompt only when needed.
3. Attach original product evidence and permitted pose/style images to the generator, with their roles. Generate one module per output.
4. Inspect the full-resolution result using `candidate_qa.py`; compare hardware crops to source and trace human anatomy. Complete human review afterward.
5. Synchronize the set. A missing/failed/stale QA report blocks completion even if a candidate says `ACCEPTED`. Missing required modules also prevent completion.

For a new risky pose or operation template, validate one representative image first. Reuse it for visible appearance consistency only after its structural review; do not batch the same unverified failure into all nine images. Deliver a per-module status table with output, template, QA report, human decision and unresolved items. Call generated-but-unreviewed sets drafts, not completed sets.
