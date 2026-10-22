# Generation templates and visual QA

Read before generating any image with people, connectors, clasps, routing, or operating instructions. Template validation checks recorded constraints, not image correctness. Inspect the generated pixels at full size before recording a result.

## Concrete generation contract

Every new generation needs a resolved `generation_template` and `quality_contract`. New Amazon modules reference a set-local pinned template catalog by ID/revision and keep quality intent in one per-image spec; the resolver supplies the following shape in memory. A standalone run may store a task-specific template with the same fields directly. Do not change the catalog to encode one SKU's product truth.

New standalone drafts additionally use `creative_policy_version: 1`, an `image_intent`, a task-specific `visual_system` (direction/lighting/typography) and `creative_brief`. Read [art-direction.md](art-direction.md) before filling them. Their purpose and visual decisions travel into the focused tool prompt and require `content_coverage` / `design_quality` review; the physical quality example below is not the complete creative specification. Legacy contracts without this policy retain their prior checks.

```json
{
  "generation_template": {
    "template_id": "lifestyle_simple",
    "revision": 1,
    "requires_human": true,
    "requires_structure": true,
    "requires_mechanism": false,
    "prompt_rules": ["Relaxed uncrossed arm; visible wearing area; preserve evidenced assembled hardware"],
    "required_checks": ["human_anatomy", "human_product_contact", "hardware_state"]
  },
  "quality_contract": {
    "version": 1,
    "layout": {
      "product_box": [0.35, 0.35, 0.90, 0.80],
      "copy_box": [0.07, 0.06, 0.70, 0.25],
      "composition": "Single model, relaxed left forearm in the foreground; wearing area sharp; title above clear of the body"
    },
    "human": {
      "present": true,
      "pose_description": "Left shoulder continues through left elbow to left wrist; palm relaxed; right hand outside frame",
      "visible_limbs": ["left upper arm", "left forearm", "left wrist and hand"],
      "contact_points": ["strap lies outside left wrist with a contact shadow; no skin clipping"],
      "occlusion_order": ["foreground left forearm in front of torso", "strap outside skin"]
    },
    "visible_hardware": ["clasp"],
    "structure_checks": [{
      "structure_id": "clasp",
      "lock_ids": ["clasp-lock"],
      "evidence_paths": ["input/01_product_evidence/clasp-closed.jpg"],
      "expected_state": "clasp_closed",
      "visible_checks": ["component count matches source", "strap routing and contact surfaces match source", "no invented hinge or floating cover"]
    }],
    "mechanism": {"depicted": false}
  }
}
```

Paths, state names and locks in this example must be replaced with actual registered evidence. `expected_state` must occur in the cited evidence's `observed_states`; a full-product photo cannot automatically prove an unseen connector. List **all visible hardware** even in lifestyle, main, size or material images. Use an empty list only when none is visible.

For an operation, set `mechanism.depicted: true` and supply `structure_id`, `action`, `start_state`, `end_state`, `evidence_paths`, and `verified_claim_ids` linked through `claim_ids`. Both states need visible evidence for that structure. Arrows, lifted/separated parts and operating copy count as an operation. A claim saying “magnetic” does not establish a hinge, release direction, or two-part opening. If evidence is missing, use a static closed detail and remove operating copy/arrows, or request the actual operating evidence if that sales task is required.

For a standalone draft, run `compile_generation_prompt.py <package> --contract <relative-contract>`. New set contracts are reference envelopes; `set_runtime.py ... prepare` resolves a focused generation prompt on demand. It includes only current lock facts, selected template rules, pose, layout, output, exact copy and a current correction when retrying. Review bookkeeping stays in the review packet. Supply the actual referenced images to the image generator; path text alone is not an image reference. Preserve the contract and generation call linkage. Do not modify a contract once a candidate exists.

## Inspection criteria

Always inspect `product_identity`, `structure_topology`, `human_presence`, `copy_claims`, and `layout_output`.

- `human_presence`: compare actual people/hands to the declaration. An unplanned person/hand is a failure and needs a revised contract; do not mark anatomy not applicable while a hand is visible.
- `human_anatomy`: trace each visible arm from its shoulder through elbow to wrist and hand, accounting for off-frame portions. Check arm ownership/count, joint direction, wrist thickness, fingers, and continuous skin contours. For crossed arms, match every overlap to the declared occlusion order. A crop may omit a joint but may not disguise an impossible connection.
- `human_product_contact`: check the actual wearing side, wrap curvature, strap thickness, contact shadow, scale, skin contact, and hardware location. Reject fused fingers, a strap inside skin or an impossible through-body loop.
- `hardware_state`: compare a full-resolution candidate crop directly with the cited original detail. Check component count, opening profile, attachment side, inside/outside faces, holes/slots, fastening surfaces, threading/routing and closed/open state. Do not judge by colour or general resemblance alone.
- `mechanism_motion`: compare each depicted state and every arrow/caption to the evidenced operation. Reject an invented hinge, lift, split, release direction or floating component.
- `copy_claims`: inspect actual rendered wording, spelling and arrows, including synonyms of unsupported claims. The script's text checks cannot establish semantic claim safety.
- `layout_output`: inspect the code-exported final and readability; check actual pixel dimensions (A+: proportional code resize to 1464×600 PNG, with a content-preserving crop only when ratios differ), undistorted proportions, product completeness, separation from copy, legibility at intended display size, and any required background. Check fine text, lines and texture after downsampling, and sharpness after enlargement. Inspect the original output, not a UI thumbnail or screenshot alone.

Save useful annotated crops or side-by-side comparisons under `qa/visual/`; they support inspection but do not become product evidence. Use `FAIL` for a visible error, `REVIEW_REQUIRED` for ambiguity, and `NOT_REVIEWED` before inspection. Do not invent observations or turn a schema/geometry pass into a visual pass.

- `content_coverage`, when an image intent exists: assess whether the actual rendered picture and/or exact copy answers the approved buyer question and relevant parent responsibility. Name the feature or benefit the buyer can understand. A filename, attractive scene or unexplained texture is not sufficient when explanation was assigned. Copy-only points need readable, supported wording, not a forced visual effect; a declared pure-atmosphere task need not illustrate a benefit.
- `module_role_fit`, for new module-language tasks: compare the rendered image with `module_language.role`, `must_show` and `not_a_substitute`. State the actual observation scale, evidence/choice/sequence or person-action-environment that performs the current job. A repeated hero may pass product identity yet fail this check; a label naming the module is not proof. Apply the current child's function, not only its parent's broad category.
- `design_quality`, when a creative brief exists: use the selected `design_recipe` when present, including its layout, task-dependent style treatment and narrative job. compare the actual focal point, hierarchy/reading path, composition/scale/depth, copy/graphic integration and contribution to the set against that brief's success criteria. A clean material render is not an automatic pass. Main-image simplicity may be deliberate; review that image's job rather than demanding effects everywhere.

  For set-linked images, compare the actual candidate with the set's other available images against shared `visual_system` background lightness/colour family, white balance, contrast/shadow depth and type family. An unplanned light/dark background switch or warm/cool grade reversal fails `design_quality`; varied scenes/surfaces within the shared range are allowed. Keep real product colours and required white main-image backgrounds. Record the visible difference and focused correction, not merely “style consistent”; equal prompt fields do not establish equal rendered style.

  For atmosphere/effect-led briefs, observe whether the named visual device actually supports the product and assigned message. Check that light, scene materials, typography and layering form a coherent relationship rather than competing focal points. Blur belongs to the declared peripheral/foreground/background region, not the focal grain, connector or proof; reflections must read as reflections rather than extra physical variants; graphic fields cannot masquerade as operating evidence. Cropping/occlusion must retain what this task needs to show. Selection/step images require clear comparison/order despite the shared styling. Record concrete clutter, contradictory lighting/scale, lost product contrast, unreadable copy or task-obscuring effects as design failures; revise the relevant device/hierarchy instead of accumulating more decoration.

## Recorded review gate

After the A+ candidate has passed [mandatory code export](state-and-contract.md#mandatory-a-code-export), or the non-A+ candidate exists:

```text
python3 scripts/candidate_qa.py <package> --contract <relative-contract> --report qa/visual/<candidate-id>.json --init
```

This creates a schema-2 draft with candidate/contract hashes, review binding, actual-composition fields and derived checks. Inspect pixels and fill `reviewer` (identify assistant versus human), each check's `status` and concrete `observation`, `composition`, and `unresolved_items`. Run the same command without `--init` to validate the record. It checks recorded observations, explicit geometry, hashes and code-export provenance; it does not use an object detector or accept a candidate. Link the report from `candidate.checks.visual.report_path` in `PRODUCT_STATE.json`. Preserve finalized reports; use a new report path for later inspections.

Only a human can accept the candidate. A visual failure cannot be hidden by a human-acceptance status for automatic set completion. For a topology/anatomy/operation failure create a replacement contract and regenerate the affected image from original evidence. Start with a simpler pose if necessary; do not polish a wrong structure. Keep the failed image quarantined. After two attempts with the same structural failure, stop that route and simplify the composition or obtain the missing evidence; do not propagate the failure through the set.

## Actual composition and review reuse

`quality_contract.layout.product_box` / `copy_box` remain target intent. Do not copy them into actual observations without looking at the final image. Record normalized `[left, top, right, bottom]` boxes in 0..1, using the final candidate's coordinates and SHA-256. Raw-image coordinates cannot be reused after cropping. Multiple product parts or text blocks use separate labelled regions.

The draft's `composition` has this shape (example coordinates only):

```json
{
  "coordinate_space": "FINAL_IMAGE",
  "image_sha256": "<current-final-image-sha256>",
  "annotation_method": "ASSISTANT_VISUAL_ESTIMATE",
  "boundary_certainty": "CLEAR",
  "required_content": "COMPLETE",
  "product_regions": [{"label": "assigned interior detail", "box": [0.40, 0.15, 1.0, 0.90]}],
  "copy_regions": [{"label": "title and body", "box": [0.02, 0.20, 0.35, 0.80]}],
  "protected_regions": [{"label": "required adjustment holes", "box": [0.75, 0.35, 0.95, 0.65]}]
}
```

`HUMAN_ANNOTATION` requires an actual human annotation; otherwise use `ASSISTANT_VISUAL_ESTIMATE`. Estimated boxes are not precise segmentation, and a claimed confidence number is not proof. Use `boundary_certainty: UNCERTAIN` for ambiguous edges and `required_content: UNCERTAIN` for uncertain completeness; these cannot pass. `INCOMPLETE` fails. Completeness follows `module_role`/`creative_brief`: full product for a full-product task, required detail for a macro, relevant wearing/contact area for lifestyle. Do not require the whole strap in every detail image. Protected regions describe observed critical content; they do not automatically turn the exporter into a composition solver.

Keep product size, hierarchy, balance and sharpness as concrete visual observations in `layout_output` / `design_quality`. Code reports box areas and overlap; it does not turn aesthetic preferences into universal thresholds. Only when the task explicitly requires them, set optional booleans in `quality_contract.layout.review_constraints`: `product_within_target`, `copy_within_target`, `product_clear_of_copy`. The first two enforce containment in the existing target boxes; the last prohibits product overlap with the target `copy_box`. These flags default off; intentional integration/overlap remains allowed. Missing or uncertain annotations require review rather than implying success.

The report's `review_binding` fingerprints the final image, review-rule version, resolved quality/design/copy/product requirements, selected reference bytes and declared comparison images. Initialize with repeated `--comparison-image <relative-image>` flags for actual set peers inspected. Declare them before inspection; changing this context requires a new report, not manually refreshing the old fingerprint. Preserve the current rule version when behavior is unchanged; increment `VISUAL_REVIEW_VERSION` when the review criteria change.

```text
python3 scripts/candidate_qa.py <package> --contract <relative-contract> --report qa/visual/<candidate-id>.json --status
```

This read-only query returns `execution`, `status`, `reason`, `next_action`, and errors. `REUSE` means the saved conclusions still apply, not that they are true with certainty: PASS awaits human acceptance, FAIL needs correction/replanning, and REVIEW_REQUIRED needs resolution or human review. `REVIEW` means an incomplete report; `INVALIDATED` means changed dependencies or a legacy report without this binding. Queries never launch generation or a visual model. A status query exits successfully when it returns a disposition; read its status before acting. Normal validation exits unsuccessfully unless the complete current report passes.

Changed image bytes, crop or typesetting require inspecting the new final. Editing text through a generative tool may alter the product too; do not skip identity/structure based only on the requested edit. This first implementation reuses the report as a whole; finer per-check reuse requires proof of which pixels/dependencies stayed unchanged. Local final-file/export checks remain necessary. Historical schema-1 reports retain their old checks and human records; do not downgrade new reports to bypass composition review.

## Real-image benchmark

Keep product-specific benchmark images and annotations outside version control and installation packages. Each case records source/provenance, actual image hash, role/layout, observed regions, expected geometry decision, annotator and whether a human confirmed it. Distinguish original web outputs from deliberately transformed negative cases. Do not label assistant observations as human ground truth or use old PASS labels as new evidence.

The repository's optional real-image regression reads `PRODUCT_COMPOSITION_BENCHMARK=<absolute-benchmark.json>` when running the standard product tests. Without a supplied dataset it explicitly skips that case. The current local WOWSTRAP baseline covers a full-product view, interior detail and two wearing scenes, plus declared mirror/crop negatives and uncertain boundaries. It tests annotation bindings and explicit geometric rules, not automatic detection accuracy, product identity or aesthetics. White-background main images, additional size/placement failures, reflections/hollow structures and human-confirmed annotations remain to be collected. Store the exact tested cases/results before adding constraints based on them.

Legacy accepted outputs remain in history. Resuming generation requires a revised draft with these fields; resuming set completion requires these template/quality fields and a matching visual QA record. For a legacy approved plan missing the fields, create a revised set rather than changing it in place. Do not revoke an existing human decision silently.
