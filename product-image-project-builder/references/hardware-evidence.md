# Hardware and operating-state evidence

Read for connector/clasp/strap-routing errors. A generated failure screenshot identifies a symptom; it cannot prove the correct product structure. Keep it in an issue record as a failure example, separate from an actual reference supplement. If only a failure image exists, leave the structure as an evidence gap and request the real detail needed for that target image. Do not recreate a missing interface from a competing product or generated thumbnail.

For each intended visible high-risk component, establish what is actually visible: component count, attachment side, inside/outside orientation, slots/holes, contact surfaces, strap routing, and assembled state. Register an original-resolution real detail with a structure ID such as `clasp` or `device_connector`; do not conflate the two. Use local identity-anchor crops when this structure repeatedly fails.

The optional `observed_states` list on each `product_evidence` record names visibly proven states of its declared structures, for example `clasp_closed`, `clasp_open`, or `connector_installed`. Register with:

```text
python3 scripts/register_product_evidence.py <package> --evidence-id clasp-closed-v1 --source input/01_product_evidence/clasp-closed.jpg --source-type REAL_PHOTO --view detail_clasp --structures clasp --hard-constraint --observed-states clasp_closed
```

Choose state IDs that identify the component. Do not add `clasp_open` when a closed photo merely suggests it could open. Opening/adjustment illustrations need evidence for both endpoints and the actual operation; before/after views alone do not establish release direction. Register operating-sequence photos and verified instructions as applicable. Static details can use only a visibly supported assembled state.

Record authoritative corrections as supplements linked to an open issue, then reconcile the production baseline/lockset. Do not mark the reported interface error resolved until a new output using the actual evidence has been reviewed by the user. Anatomical errors belong in candidate visual QA; product correction photos cannot by themselves validate a person's arm.
