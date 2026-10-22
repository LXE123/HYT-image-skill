# State, contract, and review records

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

`workflow` contains only the current control pointers. `reference_package.sha256` is the last validated `index.json` snapshot and lets package validation detect source changes. Historical run, candidate, check, and decision records stay in their arrays. Do not duplicate `evidence_mode`, `product_scope`, reference inventories, contract contents, or full geometry measurements in state.

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

New A+ tasks set `output_requirements.postprocess: CODE_CROP_RESIZE`, `format: PNG`, `width_px: 1464` and `height_px: 600`. Standalone initialization accepts `--a-plus`; grouped, generic, imported and added set tasks receive the same requirement. Existing accepted/legacy candidates stay in history; create a revised task for the new export contract rather than rewriting accepted files.

The image tool produces a retained original, not the final pixel guarantee. A set generation packet provides `raw_output_path`, final `output_path`, and the postprocess script; save the generated bytes to the raw path. Standalone work likewise keeps `<candidate>.raw.png` beside its final path. Always export using code, including when the source already has the right size. The final candidate and QA hashes refer to the exported PNG.

```text
python3 scripts/finalize_a_plus_image.py --source /path/to/product/candidates/inbox/run/image.raw.png --output /path/to/product/candidates/inbox/run/image.png --keep-box 0.05 0.25 0.95 0.75
```

Run from the single-image skill directory or use the script's absolute path. `--keep-box LEFT TOP RIGHT BOTTOM` uses 0..1 coordinates in the EXIF-oriented original and encloses ALL required product, people/action and lettering. These sample coordinates are illustrative, not a default. AI first inspects the raw image and determines that region; the code calculates an enclosing crop at the delivery ratio and performs LANCZOS resampling. It rejects a region too large to fit and never stretches or pads. Adjust the composition/regenerate rather than lying about the keep region. Matching ratios can omit the keep region. Small originals require explicit `--allow-upscale`; enlargement is recorded and must pass a sharpness/readability inspection.

The script requires Pillow (declared in the single-image `requirements.txt`); use the available image runtime. It preserves the raw file and refuses source/output identity or overwriting an existing final. To recrop before registration, choose a new output name; after a candidate/QA has been registered, use the existing revision/replacement rules so recorded hashes stay valid.

Export provenance (source path relative to the final file/SHA-256, oriented size, keep region, actual crop, target size and enlargement) is embedded in the PNG, not another workflow state file. Keep the generated original inside the product package. Review checks actual PNG dimensions and recomputes the crop from that original; missing provenance, changed originals/pixels or wrong dimensions block new A+ review/acceptance even if a report says `layout_output: PASS`. The script verifies the declared region and transformation, not whether AI correctly identified every important object or whether text is readable; visually inspect the exported image too. A separate text pass occurs BEFORE this final code export, otherwise recropping and fresh QA are required.

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
