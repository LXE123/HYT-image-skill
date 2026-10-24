# Set-plan schema

Read for initial planning or revisions. Runtime work uses [state-handoff.md](state-handoff.md) and one-image packets.

## Schema 2: one shared plan, separate image specs

When a filtered `DESIGN_INPUT.json` already has a completed image decomposition, initialize with `--design-input <path>` instead of rebuilding a default seed. The brief must identify one channel and a selected target image count, with actual child tasks covering every content group; incomplete/deferred facts remain planning work, and single-image scope uses the single-image route. This import preserves child IDs, content-group membership, exact copy, assigned roles/required proof and registered evidence IDs. It creates draft image specs, not finished creative direction or claim approval. The input snapshot records the imported source name/path and SHA-256 as provenance; task data already belongs to the existing plan/specs, so no second runtime brief file is created. Conflicting count/scope flags fail before creating the set. For both channels, use the ordinary both initializer and map the channel briefs while editing the draft.

Each imported spec carries its task-specific `image_intent` (`module_role`, `must_show`, and selected `product_facts` resolved from the task's `required_fact_ids`). Optional intake `sales_task` becomes the existing plan row's sales task. Copy dependency IDs validate copy only; they do not add facts to the visual intent. The resolver passes only this child's selected facts, never the full product/selling-point list. Unknown dependency IDs fail before set creation. Select one delivery language before import; archive other source versions without creating additional images. Group membership is stored once in `a_plus_layout.page_modules[].image_ids`; the resolver derives the current image's parent information for generation/review. Counts/readiness are likewise derived, not a persisted `image_plan` with separate statuses. Role aliases such as `craftsmanship`/`construction` and `size_and_fit` normalize to the existing detail/fit responsibilities; the assigned proof is retained. Non-main draft layout boxes are neutral until the actual creative composition is chosen.

`init_visual_set.py` now writes schema version 2. The plan owns set ID, SKU, marketplace, revision/status, input-snapshot pointer, positioning/audience/selling-point priorities, claims and the shared visual system. It also owns a pinned `template_catalog` reference (`path`, `sha256`) and compact rows:

```json
{
  "module_id": "gallery-01",
  "channel": "AMAZON_GALLERY",
  "sequence": 1,
  "required": true,
  "sales_task": "Accurate complete sellable object",
  "target_view": "front_3q",
  "template_id": "main_product",
  "template_revision": 1,
  "spec_path": "visual_sets/amazon-us-v1/modules/gallery-01.json"
}
```

The separate spec owns `module_id`, `buyer_question`, `product_references`, `pose_references`, `style_source_ids`, `prior_candidate_ids`, `required_lock_ids`, `claim_ids`, `quality_contract`, `visual_invariants`, `forbidden_changes`, `copy`, and `output_requirements`. Do not duplicate fields owned by the row or embed a full `generation_template` in the spec.

A reference retains its path, role and usage scope. Original product refs use `PRODUCT_EVIDENCE / PRODUCT_IDENTITY_ONLY`; pose refs use `POSE_ONLY / POSE_CAMERA_COMPOSITION_LIGHTING_BACKGROUND_ONLY`. Style and reviewed-candidate IDs resolve through the input snapshot. Each prior image remains opt-in, with no automatic inheritance from the previous module.

Use the [visual-quality schema](../../product-single-image-generator/references/visual-quality.md) for quality fields. It describes the resolved object; catalog templates remain shared. Output requirements specify format, aspect ratio and background. A+ requires `postprocess: CODE_CROP_RESIZE`, `format: PNG`, exact `width_px: 1464` / `height_px: 600` and the matching ratio, including ungrouped tasks; the final dimensions are established by code crop/resampling and checked from real pixels, other canvases remain archival. Gallery retains its own output requirements. Each `modules[]` row remains one independent image task, not necessarily one Amazon page module.

## A+ page grouping when selected

New plans store `deliverable` (`gallery`, `a-plus`, `both`) resolved from the instruction, `generation_mode` (`standard` or explicitly activated `expanded`), and `quantity_policy` (`scope: PER_CHANNEL`, normal range 9–15, target 13). There is no automatic channel for an unqualified request. Both normally has 26 images; 15+15 is standard. Explicit counts take precedence; 30–40 in one channel requires expanded mode, with a 40-per-channel limit. Legacy plans without these fields retain their saved scope and are not migrated on resume.

The selected department desktop A+ profile adds `a_plus_layout` to schema 2 without changing image-contract identities:

New initializations also pin the resolved count for each channel in `quantity_policy.selected_counts` (keys `AMAZON_GALLERY` and `PREMIUM_A_PLUS`, including zero for an unselected channel). Validation compares these values to the actual image-task rows, not the page groups. This prevents a thirteen-image draft from being reduced to seven rows unnoticed. An intentional in-scope count revision updates both the tasks and selected counts; local additions update the affected channel count. Older plans without selected counts keep their existing compatibility. The filtered intake's `content_groups` is not itself an executable image queue; finish its decomposition into `modules` first.

```json
{
  "profile_id": "seven-module-desktop",
  "reference_scope": "STRUCTURE_ONLY",
  "delivery": "INDIVIDUAL_IMAGES",
  "assembly_owner": "DESIGN_TEAM",
  "canvas": {"width_px": 1464, "height_px": 600},
  "page_modules": [
    {
      "page_module_id": "aplus-material-details",
      "sequence": 3,
      "display_type": "CAROUSEL",
      "content_role": "material_and_details",
      "sales_task": "Explain actual material and component details",
      "buyer_question": "What are the material and component details?",
      "image_ids": ["a-plus-03", "a-plus-04"]
    }
  ]
}
```

This excerpt illustrates one group; a complete grouped plan must cover every Premium A+ image exactly once. A full-background group contains one image; a carousel contains at least two. Group IDs/sequences must be unique and every referenced task must be an A+ task. Each child output must match the shared exact canvas and its ratio. These relationships are checked by `validate_set_plan.py` and pinned by the approved plan hash. See [a-plus-module-layout.md](a-plus-module-layout.md) for initialization, additions and department delivery boundaries. Ungrouped schema-1/2 plans need no grouping records; their A+ outputs follow the same exact canvas check. Existing accepted files stay in history; revise an old plan with another canvas before new production.

## Approval and immutability

Every claim needs a unique safe `claim_id`, claim text, status (`VERIFIED`, `SUPPORTED_WITH_CAUTION`, `NEEDS_PROOF` or `DO_NOT_USE`), `evidence_paths` and `allowed_wording`.

Approval validates:
- positioning, primary audience/motivation and at least one supported priority;
- shared direction, palette, lighting, composition, retouching and forbidden cues;
- unique module IDs/sequences, concrete sales tasks, buyer questions and covered target views;
- current locks, registered product refs and eligible style/prior-image references;
- usable claims and exact copy; operating claims must be verified;
- explicit layout, human ownership/contact/occlusion when present, all visible hardware states, and evidence-backed operation endpoints;
- current input snapshot and identity-lockset version.

The validator resolves spec files internally. Approval pins reference-file hashes in each spec and adds `spec_sha256` to each plan row, then hashes the approved plan. This binds the row, spec, shared template and source snapshot transitively. Changed approved specs or templates are rejected; create a new set/revision for intentional changes.

`materialize_module_contracts.py --module-id <id>` creates a small referenced contract. The normal `prepare` command does this just in time. Its envelope refers to the approved plan and snapshot instead of repeating templates, shared style, claims or prompts. Generation and review readers use the resolver; never manually expand all 30 contracts into the conversation.

## Legacy records

Schema 1 plans with embedded modules remain readable by validation, materialization and runtime queries. Existing accepted contracts and reports are not rewritten. New sets use schema 2; a revised set is the migration path. A legacy draft missing required quality fields still requires completion before generation.

For new quantity-policy plans, the resolver also exposes only the current image's `image_intent` (sales task, buyer question and relevant parent responsibility). Generation includes this purpose; review requires `content_coverage`. This is a human/model visual assessment of the approved task, not a claim that schema validation understands marketing content. Missing information cannot be silently replaced with unrelated imagery under an unchanged responsibility.

New initializations also store `creative_policy_version: 1` and blank `creative_brief` fields per image spec. Approval requires image-specific visual concept/device, ordered information hierarchy, graphic treatment, set role and visible success criteria. See [visual-direction.md](visual-direction.md). The resolver includes only the selected brief in its generation/review packet; `design_quality` is required when a brief is present. Legacy plans without this policy retain their prior fields and checks. Shared style stays in the plan, physical pose/layout stays in `quality_contract`; do not duplicate either in the creative brief.

## Pinned design recipes

New sets also store `design_policy_version: 1`, a pinned `design_catalog`, and `design_system` with `mode: adaptive`, default `narrative_framework_id: DIRECT`, and product/task-specific `rationale`. Adaptive mode needs no `style_id`; non-main images may use `layout_id: adaptive` and an actual `quality_contract.layout.composition`. Shared `visual_system` is derived from inputs. Each creative brief still needs its concept, hierarchy and success criteria, and may add `design_adjustments` (palette/lighting/typography/background/graphics) and `reference_influences` (`source_id`, `element`, `strength: low|medium|high`, `reason`). Influences must refer to the image's registered `style_source_ids`. These are design intentions, not numeric generator controls. Shared `visual_system.background`, `palette`, `lighting`, `typography` and `forbidden_cues` state the set background/colour/light/type range. Local adjustments and catalog recipes refine within that range; they do not independently override it. The same shared values resolve into every current-image generation/review packet; no second style state or per-image copy of the shared record is required. Explicit `mode: catalog` and old plans with no mode retain the selected `style_id` behavior. Main images still require `main_clean`; catalog layouts retain template compatibility checks. Catalog hashes and narrative stages remain checked. The generic adaptive ID is excluded from catalog-repetition warnings; actual repeated compositions still need visual review.

`configure_design.py` supplies catalog browsing, draft style/framework configuration, per-image selection/preview and explicit order changes. `order` uses all image IDs for Gallery or all page-module IDs for grouped A+, maintaining A+ membership and stable IDs. See [design-library.md](design-library.md) for the layout/style matrix, scope and original reference sources.

The runtime resolves one `design_recipe`: adaptive composition, current task adjustments and element influences, or the selected catalog recipe. Generation and review receive this object together with the shared visual system. Referenced contracts keep pointers rather than a duplicate catalog. Pinned hashes are rechecked on materializing/reviewing; mutations block stale work. Old plans acquire no new mode or requirements on resume. See [autonomous-design.md](autonomous-design.md) for research and pilot behavior.

New drafts also carry `module_language_policy_version: 1`. Current task/template and parent responsibility resolve one `module_language` for generation and review: task ID, role, buyer question, visual language, required visible content and unacceptable substitutions. An explicit `image_intent.module_role` defines the image's function, with `creative_brief.module_role` as a legacy fallback; it does not establish product facts. Review adds `module_role_fit`. Existing plans without the policy retain their original requirements; shared styling never replaces image-specific responsibilities. The new `next-generation` query selects unproduced tasks without accepting pending images.


New task specs include `execution_policy`, initially UNRESOLVED. AI fills the [input-based strategy](../../product-image-project-builder/references/automatic-intake.md#automatic-execution-strategy); code does not select by file count. `ADVANCED` and `AI_ASSISTED` are independent from quantity `generation_mode` and evidence source type. A valid assessment with NEEDS_EVIDENCE/REPLAN may remain in the plan; production/synchronization blocks that task and keeps other READY tasks selectable. Existing physical evidence/quality validation still applies, so a task missing its required facts must use the existing deferred/revision workflow. Decisions resolve from the pinned per-image spec into both contract formats, preflight and generation/review packets; review fingerprints include the decision only when present, preserving legacy report bindings. Approved changes use the normal revision rules. Legacy tasks without this field retain their previous requirements, without a silent mode migration.
