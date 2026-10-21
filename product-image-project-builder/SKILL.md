---
name: product-image-project-builder
description: Build and maintain reusable product-image evidence packages from real photos, renders, specifications and correction evidence. Use for product intake and reference updates feeding single-image or Amazon image-set generation.
---

# Product evidence packages

Own product evidence, provenance, sellable scope and gaps. The single-image skill owns image candidates/QA; the Amazon skill owns set planning and its queue. Reuse known product identity and the existing package.

## Intake before production

Inspect actual uploaded images, classify source roles and preserve originals. For mixed requirements or redesigns that still need analysis, read [automatic intake](references/automatic-intake.md): separate facts, content responsibilities, delivery constraints, exact copy and old visual suggestions; export only current production requirements. Preserve supplied copy in its original language and wording unless translation/rewrite was authorized.

Keep content groups separate from image tasks. Seven A+ module descriptions do not establish seven files. Preserve supplied job scope/count; leave an unspecified full-set count for the set planner to resolve; source groups use `content_groups`, actual children use `modules` and `content_group_id`. The set planner splits groups into meaningful child tasks before generation. The set planner normally chooses 13 for full A+; user counts/ranges and single/pilot scope take precedence. Design choices are AI proposals; they are not product facts.

Choose evidence mode from the actual inputs:

- `MODEL_ASSISTED`: useful aligned same-view render/mask pairs plus real photos.
- `PHOTO_EVIDENCE`: sufficient multi-view real photos, without requiring render masks.
- `INCOMPLETE`: evidence cannot establish the sold object or required structures; record affected tasks and gaps before production.

Resolve reversible choices internally. Ask only for necessary unresolved facts/scope, consolidate questions and continue independent authorized tasks. Reuse a supplied ID/SKU; if none is reliable, use temporary task storage until permanent registration is needed.

## Initialize or resume once

Local package root is `<system Desktop>/ProductVisualWorkspace/products/<product_id>/<version>/`. Read [storage rules](references/storage-location.md) for path resolution, overrides and collisions. Web chat uses session storage and its available tools, not the author's Desktop or local initializer.

```text
python3 scripts/initialize_package.py --product-id <id> --version <version> --evidence-mode <mode> --product-scope <scope>
python3 scripts/resolve_package_path.py --product-id <id> --version <version> --require-existing
```

Initialization creates directories and empty control records; AI still needs to analyze/register evidence and fill identity facts. Resume only a complete matching package. A partial/conflicting package needs recovery or a new version; do not overwrite it.

During this initial intake, split supplied product features and selling points into atomic `product.facts`, retaining their sources and support status in the intake archive. A supplied marketing sentence is not automatically a verified fact. Reuse this analysis for later images; decide visual versus copy-only treatment when planning the actual image, not while creating empty directories. Follow the dependency/copy boundary in [automatic intake](references/automatic-intake.md).

Initialization uses Python's standard library. Read [runtime bootstrap](references/runtime-bootstrap.md) only when image-processing dependencies are actually missing. It describes package-local runtime setup and the explicit opt-in for system software installation.

## Register what the evidence can prove

Register each independent full view/detail in `input/01_product_evidence/` with `scripts/register_product_evidence.py`. Record its source type, view, covered structures and observed states. Error-correction photos go in `input/03_error_supplements/`. A failed generated image identifies a defect; it is not correct-structure evidence.

Evidence sufficiency depends on coverage and clarity, not a fixed photo count. Require the sold object's silhouette and the structures needed for current views. In `PHOTO_EVIDENCE`, at least one registered real photo is a hard constraint; do not fabricate masks or infer unseen geometry. Clean renders contain no engineering labels/dimensions or non-product overlays. Register render templates only with useful aligned masks. Use optional part/depth/normal passes or local identity-anchor crops for demonstrated structural risks, not every product.

Operating claims require observed state evidence; a static closed photo does not establish a release motion. For recurrent connectors/clasps/routing errors, read [hardware evidence](references/hardware-evidence.md). Preserve correction provenance and related issue IDs. Issues stay open until a generation using the supplement is reviewed; `resolved/verified` requires real user confirmation.

## Validate and hand off

Run `python3 scripts/check_package.py <package>` after evidence changes; consult [schema](references/schema.md) for record problems. A changed reference hash sets `REFERENCE_CHANGED`; the single-image skill reconciles dependent locks/contracts/candidates. Do not silently revoke accepted work or mark evidence as visually verified from a script pass.

Hand off package path, product/SKU/version, validated reference hash, readiness and unresolved gap IDs. Production reads selected originals plus the filtered requirements, not the whole intake transcript or all old layouts. Same-chat exports/role changes do not establish independent context isolation.
