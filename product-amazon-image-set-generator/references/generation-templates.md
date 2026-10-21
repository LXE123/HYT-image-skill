# Concrete Amazon generation templates

Read when filling a set plan. The versioned machine-readable catalog is [generation-templates.json](../assets/generation-templates.json). `init_visual_set.py` snapshots it once in the set and records only a template ID/revision in each plan row; normalized product/copy boxes live in the separate module spec. These remain drafts until evidence and pose/layout details are filled. Coordinates are fractions of that module's own canvas, not an Amazon platform specification. Confirm current marketplace size/rule requirements separately when preparing an actual listing.

## Default sequence and composition

Choose Gallery, A+, or both from the user's instruction/context. Normal planning is 9–15 per selected channel, usually 13. A+ uses the [desktop structure](a-plus-module-layout.md) with 1464 × 600 outputs; Gallery uses its own main/secondary canvases. There is no automatic A+-only scope. Use the user's requested count/channel. The nine-role base sequence is a planning starting point, not a platform rule or a reason to invent unsupported features. Replace an unsupported module with a supported sales task or mark it blocked; never fabricate a mechanism to fill slot six.

| Gallery | Template | Concrete visual task | Required evidence and checks |
|---|---|---|---|
| 1 | `main_product` | Complete product centered on white; no copy or people | Sellable boundary/full silhouette; all visible connectors checked |
| 2 | `product_overview` | Product proposition with task-specific image/copy relationships | Covered alternate view; no invented accessories |
| 3 | `material_macro` | Real weave/surface closeup with recognizable context | Actual texture direction and scale; no fictional layers |
| 4 | `hardware_static` | Signature detail in one evidenced assembled state | Local state evidence, required locks, routing/contact profile |
| 5 | `hardware_static` | Connector/clasp construction from a different supported angle | Own interface evidence; do not repeat slot four without a distinct task |
| 6 | `mechanism_steps` | Demonstrate only a proven adjustment/release motion | Start/end evidence and verified operating claim; otherwise replace with static task |
| 7 | `size_fit` | Verified size/compatibility guidance with clean labels | Specs and claims for this SKU; no unsupported device |
| 8 | `lifestyle_simple` | Assigned meaningful person/action/environment with naturally readable product | Anatomy ownership, contact/occlusion, visible hardware state |
| 9 | `range_story` | Registered variants or single-product closing composition | Each variant's source; no invented colours |

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
