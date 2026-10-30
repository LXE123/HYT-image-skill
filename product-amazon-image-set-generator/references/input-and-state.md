# Input and set-state model

Production state, plans, snapshots, contracts and visual reports are records in `PROJECT.sqlite3`. Names below are query addresses; see [database runtime](../../product-single-image-generator/references/database-runtime.md). Original evidence and commercial source files stay on disk.

All paths are relative to the shared product root `<system Desktop>/ProductVisualWorkspace/products/<product_id>/<version>/`.

## Source precedence

1. Current explicit user instruction.
2. Registered real product evidence and approved render/mask evidence.
3. Verified product specifications and claim proof.
4. Approved brand system and set plan.
5. Style, pose, and competitor references.

Lower levels never overwrite higher levels.

Mixed requirement documents first follow the builder's [automatic intake](../../product-image-project-builder/references/automatic-intake.md). Raw document registrations are an audit archive, not automatic production context. Redesigning a submission does not promote its old layouts, colours or finished examples to BRAND_GUIDELINE/STYLE_REFERENCE. The design stage uses a filtered brief and explicitly selected original evidence; do not pass the raw manifest, source text, old visual descriptions or original workbook by default. Runtime tool/context boundaries are separate from source hashes. Resolve reversible choices internally rather than requiring approval of every parsed field.

## Commercial source manifest

Store normalized source registrations at `commercial/source_manifest.json`:

```json
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "listing-copy-v1",
      "path": "commercial/sources/listing.json",
      "role": "LISTING_COPY",
      "sha256": "...",
      "source": "seller export",
      "retrieved_at": "2026-10-10T00:00:00Z"
    }
  ]
}
```

Allowed roles:

- `LISTING_COPY`: title, bullets, description, search-facing wording.
- `PRODUCT_SPEC`: dimensions, compatibility, materials, included items, variants.
- `CLAIM_EVIDENCE`: supplier declaration, certification, or test evidence.
- `BRAND_GUIDELINE`: approved palette, typography, logo, tone, and casting rules.
- `MARKETPLACE_RULE`: dated marketplace requirement snapshot.
- `STYLE_REFERENCE`: mood, hierarchy, spacing, lighting, and graphic language only.
- `POSE_REFERENCE`: camera, pose, perspective, and composition only.
- `COMPETITOR_REFERENCE`: comparative market context; never product identity evidence.

Every local source needs a valid root-relative path and SHA-256. A marketplace snapshot also needs a URL/source and retrieval date. Preserve original source files; add a new source ID/version instead of overwriting history.

## Input snapshot

`init_visual_set.py` writes `visual_sets/<set_id>/INPUT_SNAPSHOT.json` containing:

- product ID, SKU, marketplace, and creation time;
- `index.json` path/hash and identity-lockset version;
- commercial manifest path/hash and source records;
- eligible upstream candidate records;
- excluded candidates and exact exclusion reasons.
- the identity lockset and sellable-object scope, stored once so referenced contracts can recover the same facts after interruption.
- optional `design_brief` source provenance (source path and SHA-256) when initialization uses `--design-input`; imported requirements live in existing task records, not a second runtime brief. Older copied-brief records remain readable.

Eligible upstream candidate statuses:

- `ACCEPTED`: may support visible cross-view, colour-rendering, and set-style consistency.
- `HUMAN_STRUCTURE_REVIEW_PASSED`: may support visible cross-view consistency only.

The candidate file/hash, source contract, SKU, and lockset version must match current state. Exclude pending, rejected, stale, missing, or hash-mismatched candidates.

## Set state

`visual_sets/<set_id>/SET_STATE.json` is the set control plane:

```json
{
  "schema_version": 1,
  "set_id": "amazon-us-v1",
  "marketplace": "AMAZON_US",
  "status": "SET_PLAN_DRAFT",
  "plan_revision": 1,
  "plan_path": "visual_sets/amazon-us-v1/SET_PLAN.json",
  "input_snapshot": "visual_sets/amazon-us-v1/INPUT_SNAPSHOT.json",
  "modules": [],
  "next_action": "COMPLETE_COMMERCIAL_INPUTS_AND_PLAN"
}
```

Statuses:

- `SET_PLAN_DRAFT`
- `PLAN_APPROVED`
- `MODULE_CONTRACTS_READY`
- `MODULES_GENERATING`
- `SET_REVIEW`
- `COMPLETE`
- `BLOCKED`

`PRODUCT_STATE.json.visual_sets` is a query projection derived from set rows, not another saved summary. Module history belongs to the corresponding set/module rows.

For routine execution query `set_runtime.py ... next`; do not load these full files into the conversation. New plan schema 2 uses a compact module index, separate per-image specs and one pinned template catalog. See [state-handoff.md](state-handoff.md). Module state may include `attempt`, `attempt_history`, candidate/contract pointers and accepted output hashes. Attempt history contains decisions and pointers, not prompts or review narratives. Candidate decisions and derived set/module statuses now commit together in one SQLite transaction; `sync` reconciles evidence/QA changes rather than repairing a split commit.
