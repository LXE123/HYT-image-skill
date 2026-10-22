---
name: product-amazon-image-set-generator
description: Plan and produce Amazon Gallery images, Premium A+ images, or both from an existing product package. Separate content groups from individual image tasks; normally 9-15 images per selected channel, usually 13. Use the single-image skill for one requested image.
---

# Amazon image sets

Own scope, image planning, coverage and the production queue. Reuse existing plan/spec/state records; derive summaries instead of adding parallel plans, status stores or workflow services. `product-image-project-builder` owns product evidence; `product-single-image-generator` owns generation and visual QA. Reuse the current package and known requirements.

Activate supporting instructions according to the current task and information gap. Preserve complete guidance and examples for the cases that need them; text/file size is not a reason to remove useful requirements. Follow links when planning, designing, inspecting or troubleshooting requires that material, not as a checklist to load the whole skill directory. Reuse completed intake, saved image ledgers and resolved current-image packets. Revisit source material when the evidence, task or criteria change, or a specific uncertainty needs verification.

## 1. Resolve the requested work

Use the user's instruction or saved scope: Gallery, A+, or both. Ask once only if an unqualified set request leaves this unresolved. An A+ example alone does not request A+ production. A standalone image goes to the single-image skill; an explicit pilot keeps its requested count.

Normally plan 13 images per selected channel, adapting within 9–15 for meaningful coverage. Explicit counts/ranges take precedence; both normally means 13+13. Expanded mode (30–40 per channel, fallback 36) requires an explicit large-production request. New defaults never expand a saved queue.

For this department, A+ delivers only a code-exported 1464×600 PNG. Generate a suitable wide composition, retain the original and run the single-image [code export](../product-single-image-generator/references/state-and-contract.md#mandatory-a-code-export) before review; model-native pixels are not trusted as final dimensions. Matching ratios resize proportionally without cropping; mismatched ratios crop around required content and resize proportionally, without stretching or padding. Gallery uses its own canvas (square by default). Archive older/mobile canvas requirements without producing extra versions. Select the current delivery language from the task/market; archived translations do not request additional outputs. Deliver independent files for design-team assembly. Each may contain related panels, copy, graphics, comparisons or steps serving its assigned task.

Prioritize **2.44:1 (1464:600)** landscape framing during A+ generation, before style/reference framing or local layout choices. Put it first in every image prompt and use supported size/ratio controls when available; follow the single-image [export guidance](../product-single-image-generator/references/state-and-contract.md#mandatory-a-code-export) for tool limits. Exact delivery pixels still require code export.

## 2. Turn responsibilities into an image plan

**Content group ≠ output image.** Seven module descriptions are seven responsibilities, not seven photographs. Use [A+ grouping](references/a-plus-module-layout.md) when establishing/revising grouping or choosing a seed, or [Gallery coverage](references/amazon-planning.md) when planning Gallery coverage. A complete saved ledger can be reused directly. The nine-image A+ seed is `1+1+2+2+1+1+1`; it is revisable, not a required content list.

Before generation, save the selected image count and a compact ledger: group → child image IDs → buyer question/required proof → visual treatment/copy → status/output. Child counts must sum to the selected target. Generate and count child IDs, not group headings. Missing evidence stays visible on affected tasks; do not invent a variant, size, operation or care claim, or substitute an unrelated macro under that label. Explicit replanning updates the responsibility and its reason.

For mixed requirement sheets/redesigns, read the builder's [intake workflow](../product-image-project-builder/references/automatic-intake.md). Carry the supplied scope/count, `content_groups` and decomposed `modules` forward. The planner resolves an unspecified target, then checks actual child count, group coverage and fact gaps; readiness is computed from these records rather than stored as another state object. Keep source copy verbatim in its selected language; Chinese analysis is not image lettering. Originals establish product truth; design references guide only their assigned visual elements. Old layouts remain archival in a redesign unless currently requested.

Reuse the builder's atomic facts/selling points; do not reparse all uploads for each image. Map required features and buyer questions onto the existing children before choosing scenes. Identify what the picture should visibly communicate and what belongs only in exact copy. Mix these treatments within an image when useful. Pure atmosphere is allowed when assigned, but cannot replace required feature, operation or selection information. Do not force every selling point into visual effects, impose a lifestyle quota, or attach the full selling-point list to every prompt.

## 3. Design before generating

When creating or revising design decisions, use [visual direction](references/visual-direction.md) to set one shared visual language and each image's `creative_brief`: concept, visible device, hierarchy, graphic treatment, contribution and success criteria. Execute an already complete brief through its current task packet rather than reopening design planning for every image. Default to `adaptive`; derive composition from the job. Fix the shared background lightness/colour family, warm–cool balance, contrast/shadow range and type family in the existing `visual_system` before individual design. Per-image adjustments and catalog styles stay within those boundaries; composition, scene, camera and surface may vary. A request for unified backgrounds does not permit independently alternating dark and light pages. A material image, selection guide, operation and lifestyle need their own visual proof within the shared language. Full lifestyle assignments need recognizable people/actions/environments and a readable, naturally scaled product.

Use [autonomous execution](references/autonomous-design.md) for research or an internal pilot. AI chooses reversible design details, checks representative images, then continues the authorized batch. Consolidate only necessary product-truth/scope questions; continue independent tasks. Image acceptance still requires real human feedback.

Optional references, only when needed: [style/reference integration](references/product-led-style-integration.md), [catalog layouts/styles](references/design-library.md), [template constraints](references/generation-templates.md), [claim wording](references/claim-safety.md). A catalog selection does not complete the creative brief.

## 4. Execute in the available environment

**Web chat:** read [browser testing](references/browser-testing.md) and use the same ledger with available tools. Do not load the local runtime/schema references unless actually running scripts. Ordinary attachments do not install skills or grant local tools. Check actual image viewing and image-tool attachment support once; report capability limits honestly.

**Script runtime:** read [state handoff](references/state-handoff.md) once; use [schema](references/set-plan-schema.md) only while editing records and [source/state details](references/input-and-state.md) for provenance problems. From this skill's directory:

```text
python3 scripts/init_visual_set.py <package> --set-id <set> --deliverable a-plus --count <selected-count>
python3 scripts/init_visual_set.py <package> --set-id <set> --design-input <filtered-DESIGN_INPUT.json>
python3 scripts/validate_set_plan.py <package> --set-id <set> --approve
python3 scripts/set_runtime.py <package> --set-id <set> next-generation
python3 scripts/set_runtime.py <package> --set-id <set> prepare --module-id <returned-id>
```

Choose one initialization route. A completed single-channel filtered brief imports its actual image IDs, grouping, copy, roles and evidence links; an undecomposed brief must be finished first. Without it, initialization creates a seed for AI to adapt. `--deliverable gallery/both` selects those channels; per-channel count flags override `--count`. Resume existing work instead of initializing it again. `--approve` pins an executable plan internally, not human image acceptance.

Batch production uses `next-generation` to select an unproduced child. Ordinary `next` prioritizes pending review; a repeated ID requests inspection, not another generation. Send only the current packet's prompt and actual listed images to the generator. Re-establish this child's role before each call; previous outputs/history are not automatic references. The scripts prepare records and packets; they do not launch image generation or erase chat context.

## 5. Review, correct and deliver

Use single-image QA on actual pixels: product truth, relevant anatomy/hardware/operation, exact copy and canvas, buyer-question coverage, role fit and design quality. A script pass verifies records, not appearance. Keep candidates pending human review while producing other authorized tasks. Focused feedback authorizes correction of that image; reuse evidence and preserve unrelated outputs. Pinned changes need a local revision; retry limits and acceptance records follow [state handoff](references/state-handoff.md).

Before handoff, reconcile target/planned/generated/deferred counts, responsibility coverage, repeated messages and visual rhythm. Compare the actual images together for background lightness, colour temperature, contrast/shadows and typography; an individually attractive image that drifts from the shared range needs a focused correction. Deliver files with grouping, copy guidance and clear statuses. `set_runtime.py ... handoff` returns the manifest; it does not stitch, upload or certify the assembled page. Call unreviewed images drafts; never fabricate human acceptance.
