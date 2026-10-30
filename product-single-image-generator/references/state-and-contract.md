# State, contract, and review records

Production JSON names in this guide are SQLite record addresses. Use [database runtime](database-runtime.md) to query/fill drafts and record decisions; do not create parallel state files. Schema examples below describe returned objects.

Use paths relative to `<system Desktop>/ProductVisualWorkspace/products/<product_id>/<version>/`. `index.json` owns reference evidence. `PRODUCT_STATE.json` owns workflow state and decisions. Contracts and QA reports are immutable snapshots; the state points to them rather than copying their full contents.

## `PRODUCT_STATE.json`

New packages use this core shape. Existing schema-version 1 packages may be resumed; initialize the missing `workflow` object without deleting historical fields.

```json
{
  "schema_version": 2,
  "product_id": "PRODUCT_ID",
  "sku": "SKU_OR_VARIANT",
  "reference_package": {"path": "index.json", "version": "VERSION", "sha256": "..."},
  "sellable_object": {"included": [], "excluded": []},
  "product_identity_baseline": {
    "status": "READY | PROVISIONAL | INCOMPLETE",
    "visual_invariants": [],
    "surface_topology": [],
    "view_constraints": []
  },
  "identity_lockset": {"version": 1, "status": "INCOMPLETE | READY", "locks": []},
  "workflow": {
    "status": "REFERENCE_INTAKE",
    "active_run_id": null,
    "active_view": null,
    "active_contract": null,
    "active_candidate_id": null,
    "geometry": {"status": "NOT_REQUESTED"},
    "next_action": "ADD_AND_VALIDATE_REFERENCES"
  },
  "evidence_gaps": [],
  "runs": [],
  "candidates": [],
  "geometry_checks": [],
  "decision_log": []
}
```

`workflow` contains only the current control pointers. `reference_package.sha256` is the last validated `index.json` snapshot and lets package validation detect source changes. Historical runs, candidates, checks and decisions are stored as database rows and projected into these arrays when requested. Do not duplicate `evidence_mode`, `product_scope`, reference inventories, contract contents, or full geometry measurements in state.

Use these workflow statuses:

- `REFERENCE_INTAKE`: source package is incomplete.
- `REFERENCE_READY`: source package is usable for baseline/lock preparation.
- `REFERENCE_CHANGED`: new evidence may stale active production records.
- `CONTRACT_DRAFT`: active contract still needs evidence-backed constraints.
- `GENERATION_READY`: preflight passed for the active contract.
- `CANDIDATE_CREATED`: the contract output exists and is awaiting checks/review.
- `HUMAN_REVIEW`: automated checks are complete, unavailable, or intentionally skipped.
- `ACCEPTED`, `REJECTED`, or `BLOCKED`: current run reached a human decision or evidence stop.

Each lock needs `lock_id`, `fact`, `affected_views`, `status`, and an evidence reason. A full-view lock uses `render_template_id`, resolving to `index.json`. A high-risk local lock uses `anchor_id`, resolving to `qa/identity_anchors/index.json`. Retain changed locks as history.

For a correction, add a decision with `issue_id`, source path/hash, corrected fact, affected baseline fields, run IDs/candidate IDs, and action (`CONTRACT_REPLACED`, `CANDIDATE_REJECTED`, or `REVIEW_REQUIRED`). Retain old contracts and mark affected ones `STALE_AFTER_CORRECTION`.

## Per-view generation contract

Create one immutable contract per candidate:

```json
{
  "schema_version": 2,
  "run_id": "RUN_ID",
  "candidate_id": "RUN_ID-VIEW",
  "sku": "SKU_OR_VARIANT",
  "target_view": "VIEW_ID",
  "identity_lockset_version": 1,
  "required_lock_ids": [],
  "references": [
    {"path": "...", "role": "PRODUCT_EVIDENCE", "usage_scope": "PRODUCT_IDENTITY_ONLY"},
    {"path": "...", "role": "POSE_ONLY", "usage_scope": "POSE_CAMERA_COMPOSITION_LIGHTING_BACKGROUND_ONLY"}
  ],
  "prior_candidate_references": [],
  "visual_invariants": [],
  "forbidden_changes": [],
  "output_requirements": {"format": "PNG", "background": "white"},
  "output_path": "candidates/inbox/RUN_ID/RUN_ID-VIEW.png"
}
```

Do not overwrite a contract after it has produced a candidate. Create a new run or candidate contract. Do not list rejected candidates as prior references. An accepted candidate used for cross-view consistency needs an explicit limited scope and cannot supply unseen structure.

New standalone initialization keeps schema version 2 and adds `creative_policy_version: 1`, `prompt_format: focused-v1`, blank `image_intent`, `visual_system` and `creative_brief`. Complete the current image's design decisions from [art-direction.md](art-direction.md) before compiling. The policy requires both content and design review; deleting a brief does not disable them. This does not migrate or invalidate an existing legacy contract or accepted candidate.

The resolved generation view also requires `generation_template`, `quality_contract`, `resolved_identity_locks`, and `generation_prompt` from [visual-quality.md](visual-quality.md). Standalone/legacy embedded contracts store these fields directly. New set contracts use schema version 2 with `storage_mode: REFERENCED`: the disk envelope contains candidate/run/SKU/view, lockset version, output path, set linkage, attempt, optional current correction, and `bindings.plan` (path plus SHA-256); the approved plan already pins its input snapshot, so new envelopes derive that binding. Older explicit `bindings.snapshot` values remain checked for consistency. `context_store.load_contract` expands only that module and its selected claims/facts. Do not write the expanded object back into the envelope. Approved plan module hashes and a pinned catalog bind all transitive inputs. Candidate `checks.visual.report_path` links the visual report separately from geometry; neither check substitutes for the human decision.

## Mandatory A+ code export

New A+ tasks set `output_requirements.postprocess: CODE_CROP_RESIZE`, `pre_crop_review: OBSERVED_LAYOUT_V1`, `format: PNG`, `width_px: 1464` and `height_px: 600`. Standalone initialization accepts `--a-plus`; grouped, generic, imported and added set tasks receive the same requirement. Existing tasks without `pre_crop_review` retain their original export contract; use a revised task to apply the guard, never rewrite accepted files.

At generation time, prioritize **2.44:1 (1464:600)** landscape framing over style/reference aspect ratios and local layout choices. Put the ratio at the start of the prompt and compose all required content for that frame. Use ratio/size parameters only when the current tool actually exposes them; `output_requirements.aspect_ratio` is contract data, not proof that a tool accepts that argument. The current built-in tool is prompt-controlled. Do not switch to an API/CLI workflow solely for size control.

For an already authorized API workflow with a compatible model, [OpenAI's image API reference](https://developers.openai.com/api/reference/resources/images/methods/generate) supports custom `size` subject to model limits, including dimensions divisible by 16. For example, `size: 1952x800` has the exact 2.44:1 ratio and can be proportionally reduced to 1464×600; it is a compatible source-size example, not a new delivery canvas. Do not send 1464×600 to an interface requiring multiples of 16. If the current tool lacks exact ratio control, request 2.44:1 explicitly and use the closest supported landscape canvas, then preserve content during code export. Always inspect actual output dimensions rather than assuming the request succeeded.

The image tool produces a retained original, not the final pixel guarantee. A set generation packet provides `raw_output_path`, final `output_path`, and the postprocess script; save the generated bytes to the raw path. Standalone work likewise keeps `<candidate>.raw.png` beside its final path. Always export using code, including when the source already has the right size. The final candidate and QA hashes refer to the exported PNG.

For a new guarded task, initialize a source QA report before the final exists (commands run from the single-image skill):

```text
python3 scripts/candidate_qa.py /path/to/product --contract runs/run/image_generation_contract.json --report qa/visual/image-source.json --init --source-image candidates/inbox/run/image.raw.png
python3 scripts/finalize_a_plus_image.py --source /path/to/product/candidates/inbox/run/image.raw.png --output /path/to/product/candidates/inbox/run/image.png --package /path/to/product --contract runs/run/image_generation_contract.json --review qa/visual/image-source.json --check-only
```

Inspect the actual source and fill the report's `composition` using `SOURCE_IMAGE` coordinates, reviewer and completeness/uncertainty fields. Source QA uses the existing report type, not another queue/state machine. It contains only layout/design checks and cannot be accepted as a final visual report. The first check may request annotation before it can propose a crop; finish that source observation, then query again. The guard derives a keep-region union from product/copy/protected regions when ratios differ, or verifies an explicit `--keep-box`. All required regions must survive. It projects them into `PROJECTED_FINAL` coordinates, checks the contract's explicit layout constraints, and returns the proposed `normalized_crop_box` plus reasons/metrics.

Inspect that exact crop for required content, product scale, copy usability and balance. Fill `reviewed_crop_box` with the returned normalized source crop, and record actual `layout_output` / `design_quality` observations. These are internal assistant/human inspection records, not a new mandatory user-approval gate. Failed or uncertain conclusions block export. Code does not infer visual balance from percentages. Do not change an observation to PASS simply to run the command. Recompose/regenerate when necessary; automatic background extension is not included.

Run the export command without `--check-only` once the guard passes. A check-only query writes no image and its successful process exit does not mean the disposition was PASS. A source review with a different candidate, source hash, contract, evidence, rules or reviewed crop cannot authorize export. Afterward initialize a separate final QA report at `qa/visual/image.json`; inspect the actual final in `FINAL_IMAGE` coordinates. Source and final reports describe different image stages, not duplicate approvals.

Run from the single-image skill directory or use the script's absolute path. The same script handles both cases; keep the existing `CODE_CROP_RESIZE` contract:

- Matching aspect ratio (1464:600): omit `--keep-box` and resize the full frame proportionally, without cropping. For example, 2928×1200 becomes 1464×600. An already exact-size image keeps its pixels and still receives export provenance in a separate file.
- Different aspect ratio: inspect the raw image, then supply `--keep-box LEFT TOP RIGHT BOTTOM` in 0..1 coordinates in the EXIF-oriented original, enclosing ALL required product, people/action and lettering. The code calculates an enclosing crop at the delivery ratio and performs proportional LANCZOS resampling. The sample coordinates above are illustrative, not a default. It rejects a region too large to fit; adjust the composition/regenerate rather than omitting important content from the declared region.

Never independently scale width and height to force the target size, or pad. Small originals require explicit `--allow-upscale`; enlargement is recorded. Inspect final-size text, fine lines and texture after either operation: downsampling can lose detail, and enlargement cannot restore missing detail. Exact pixels and preserved proportions do not establish sharpness/readability.

The script requires Pillow (declared in the single-image `requirements.txt`); use the available image runtime. It preserves the raw file and refuses source/output identity or overwriting an existing final. To recrop before registration, choose a new output name; after a candidate/QA has been registered, use the existing revision/replacement rules so recorded hashes stay valid.

Export provenance (source path relative to the final file/SHA-256, oriented size, keep region, actual crop, target size and enlargement) is embedded in the PNG, not another workflow state file. Guarded exports also bind the source QA report and contract paths/hashes. Preserve those source records; later inspection uses a new report path. Keep the generated original inside the product package. Review checks actual pixels, recomputes the crop and rechecks its source layout authorization; a missing/changed source review blocks guarded-task review even if a final report says PASS. Code verifies declarations and transformations, not object detection or text readability. A separate text pass occurs BEFORE this final code export, otherwise recropping and fresh QA are required.

If there is no code runtime or Pillow support, the exact export remains unfinished. An image-tool promise of 1464×600 or an HTML preview cannot substitute for execution. This postprocessing transforms an AI-generated image; it is not permission to construct product imagery from source-photo collages.

## Candidate and check status are separate

Candidate decisions:

- `PENDING_REVIEW`
- `REJECTED_TOPOLOGY`
- `REJECTED_VISUAL`
- `HUMAN_STRUCTURE_REVIEW_PASSED`
- `ACCEPTED`

Geometry check results:

- `NOT_REQUESTED`
- `REVIEW_REQUIRED_NO_TEMPLATE`
- `REVIEW_REQUIRED`
- `AUTO_PASSED`
- `REJECTED`

Never use a geometry result as the candidate decision. Store the compact geometry summary under the candidate's `checks.geometry` and in `geometry_checks`; keep measurements, overlays, hashes, and configuration in the report directory.

## Human review record

For each review, record candidate ID/hash, reviewer authority, source contract, decision, checked items, unresolved items, and follow-up. Cover sellable-object boundary, variant, silhouette, components, connectors, fastening, routing, overlaps, visible surfaces, target-view proportions, material/colour/orientation, completeness, background, crop, and text constraints.


## Structure state transfer

Natural-language reasoning and code share current `PRODUCT_STATE.json`; they do not maintain separate semantic documents. AI interprets original multi-view evidence and proposes a state delta. Code validates evidence identity, prior-state hashes and dependencies, applies the delta, and derives task/review inputs. History remains for traceability and is not appended to generation prompts. This implements structure feedback only; the broader evidence-mode design remains a proposal.

Distinguish **wrong candidate pixels** from **wrong/incomplete product interpretation**. A generation defect with correct source facts needs a rejected candidate and a focused replacement task, not a change to product truth. If the interpretation was incomplete, revise the corresponding lock from original evidence. If it remains uncertain, use `REVIEW_REQUIRED`; do not convert user rejection or an AI guess into a new confirmed fact. Code validates the transfer, not the meaning or visual accuracy.

Use fine-grained, reusable structure locks for independent structures. Existing coarse locks conservatively invalidate all their dependants; AI may split them in a new task/plan revision. The updater can add locks but cannot infer a decomposition or reassign task dependencies. Never drop a required structure just to bypass a stale-state check.

A lock may add `evidence_paths` and `relations`. Relations describe actual product parts and surfaces, not fixed page coordinates. Their vocabulary is product-derived; no product-specific part list is built into code. For example, inside a complete existing lock:

```json
{
  "evidence_paths": ["input/01_product_evidence/actual-rear.jpg"],
  "relations": [{
    "relation_id": "inner-relief",
    "subject": "observed recessed area",
    "predicate": "belongs to the inner face of",
    "object": "observed panel",
    "views": ["back_3q"],
    "evidence_paths": ["input/01_product_evidence/actual-rear.jpg"]
  }]
}
```

Use actual registered paths and view names. Omit `views` only when the relation applies to every task using the lock. AI must determine visibility/occlusion for the requested view; code only selects authored applicability. Evidence needed for applicable relations must be included in the current task's product references. A pose image cannot become authority for another product's structure.

Propose a temporary JSON delta with `reason`, optional package-relative `source_report`, and `updates`. Each update contains `lock_id`, `expected_lock_sha256` and a complete `replacement` lock. Compute the prior-lock hash with `structure_state.value_hash` (canonical JSON); use null only for a new lock ID. Preserve existing fields, explicitly replace incorrect values, cite registered original `evidence_paths`, and choose `LOCKED` or `REVIEW_REQUIRED`. Supplied source reports must match registered candidate/contract bytes and contain an observed failure/uncertainty. Do not append old and contradictory facts to the replacement. The delta is command input, not another live state store.

```text
python3 scripts/revise_structure_state.py <package> --change <temporary-delta.json> --expected-state-sha <current-PRODUCT_STATE-record-SHA256>
```

The updater changes only current locks and a compact decision-log entry, increments the lockset version, and commits them together in a short `BEGIN IMMEDIATE` transaction after checking the expected record hash. It does not rewrite source photos, approved plans, old contracts, candidates, QA reports or human decisions. `READY` at lockset level remains a record-level condition; individual unresolved locks block dependent tasks. All production writers use the same project transaction interface.

Run set synchronization after applying a delta. It derives blocked children from actual required-lock contents/status, not merely the global version. Unchanged lock dependencies may continue under their original pinned contracts and QA; changed or unresolved dependencies require revised tasks. Reference/index changes still use the existing conservative source-change path. Approved affected plans need a new revision and current snapshot; do not patch their immutable files. Standalone drafts without candidates can compile current selected locks; natural-language analysis must also revise any conflicting task copy/layout/intent. Existing candidate contracts remain immutable.

Current-view relations appear in focused generation/review packets. Final QA initialization adds `structure_observations` keyed by `lock_id:relation_id`, initially `NOT_REVIEWED`. For each required relation, inspect actual pixels against originals and record status plus a concrete natural-language `observation`. Missing, failed or uncertain relation observations prevent QA PASS even if the general topology check passes. Valid old reviews are invalidated when their selected structure dependencies change; scripts never auto-accept an image. Legacy contracts/reviews without relation data keep their prior fields; relations are activated through explicit state/task revisions.

In web execution without scripts, apply the same current-state delta and dependent-task selection in existing records, keep version/evidence pointers, and report that code checks were not run. Do not substitute a growing conversation summary for updated product state.
