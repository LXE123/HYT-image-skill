# State handoff and bounded working input

Use this execution reference once when starting or resuming production. Further iterations use concise script results, not rereads of every skill/reference.

## Stored state versus current working input

The control plane contains IDs, versions, status, attempt numbers and artifact pointers. Current image generation still requires actual product facts, a selected template, exact copy and relevant images. Scripts retrieve those from pinned files for this one image; they do not summarize previous conversations into new instructions.

New sets use these ownership boundaries:

| File | Owns | Read into model context |
|---|---|---|
| `SET_PLAN.json` | Shared visual system/claims plus compact module index | At planning time; use query output in production |
| `TEMPLATES.json` | One pinned version of each reusable template | Only the selected template's generation rules |
| `modules/<id>.json` | One image's refs, copy, pose/layout/quality intent | Only when planning or revising that image |
| `INPUT_SNAPSHOT.json` | Shared evidence versions, identity facts, eligible references | Script selects required facts; no full history dump |
| `SET_STATE.json` | Queue progress and candidate/contract pointers | Compact `next`/`status` result |
| Referenced contract | Candidate/run identity, attempt, pinned plan/snapshot pointers | Script expands in memory |
| Candidate and QA files | Output and inspection audit | Current image at review; previous reports only for explicit investigation |

Shared facts are stored once. Files are resolved and hash-checked by code. No extra “conversation summary” document is generated per image. Generation input omits QA fields, statuses, hashes and unselected modules. Review input omits prior prompts and unrelated reviews. Neither packet is a new source of product truth.

## Gallery opening pair and later design

For a new full Gallery set, load the [single-image skill](../../product-single-image-generator/SKILL.md) and follow the [opening-pair approval](amazon-planning.md#opening-pair-inspect-first-inherit-identity-rather-than-pose). Select the existing two white-display IDs with `prepare --module-id`, generate physical upright front/reverse views, inspect against originals, display both current outputs, and stop for the user's explicit approval. The pair remains part of the original nine. Resume saved outputs/QA after interruption, never generate the remainder merely because self-checks passed.

`gallery_opening_review` in new full Gallery plans identifies the two required IDs. Status/selection exposes `opening_review` and `required_skill`; after both images exist, `next-generation` returns `WAIT_FOR_GALLERY_OPENING_APPROVAL` with no remaining Gallery task selected. Both current candidates need the existing `ACCEPTED` record, valid QA and real human reviewer/decision reference. A message may approve both when it clearly refers to both displayed outputs. Record each candidate with `record --module-id <id> --decision ACCEPTED --report <QA> --human-reviewer <actual-user> --decision-reference <actual-message>`. Internal plan approval, silence, partial approval, self-QA or structure-only review cannot substitute. Corrections/retries and changed bytes require new approval of the affected current image.

The check also guards direct later-image `prepare`, generation `packet`, `materialize_module_contracts.py` and single-image generation preflight, before later generation artifacts are created. Contracts/QA/history remain in existing storage; approval is derived, not a separate phase/approval database. Saved unmarked sets retain old semantics: explicitly revise or create a new set to adopt the policy. A+ tasks and explicit pilot/single scopes retain their own policy.

The opening pair's upright pose lives in each child's layout/brief, never in the shared identity lockset. After approval later children inherit supported product facts and original evidence; multi-style pose/arrangement remains free. Save the selected arrangement in the child's brief and mandatory choices/parameters in its intent. For joint inspection declare the other current image with `--comparison-image`. Eligible prior-image use and product-state corrections follow explicit affected-task revision/snapshot rules; approval does not authorize mutation of pinned contracts or make generated images evidence for hidden structure.

## Production loop

All commands below run from this skill's directory and take the existing package path. Use one serial writer per product package; these scripts are not a multi-worker job scheduler.

```text
python3 scripts/set_runtime.py <package> --set-id <set> next
python3 scripts/set_runtime.py <package> --set-id <set> prepare
```

`next` synchronizes decisions and returns counts, one current module and the next action. `status` is a read-only view of last recorded state, augmented by discovery of already-saved outputs. `prepare` materializes only the selected module, activates its run and performs preflight. Repeating it reuses the same contract. If an image exists, it returns a review packet and never overwrites the image.

After any mandatory Gallery opening approval, for already authorized batches where the remaining planned images should be produced before grouped human review, use `next-generation` to select an unproduced ID, then call `prepare --module-id <id>`. This does not accept or discard pending candidates and does not authorize expanding the batch. The usual `next` intentionally prioritizes pending review; never interpret that repeated task as another generation request. In a web workflow without scripts, keep an explicit image-ID/task/status/output ledger and select an unproduced task from it before every call, rather than continuing from the last hero's prompt.

For generation, pass only `prompt` and references whose `kind` is `image` to the image generator. Document pointers remain available for targeted verification; do not submit a PDF/JSON guideline as an image or dump its full text into the prompt. The shared visual system should already contain the needed normalized style decisions. Save at `output_path`. Preserve image roles: original evidence controls identity; pose/style/prior images have their limited roles. Do not attach every earlier image or feed a failed image forward by default.

```text
python3 scripts/set_runtime.py <package> --set-id <set> record --module-id <id> --decision PENDING_REVIEW
python3 scripts/set_runtime.py <package> --set-id <set> packet --module-id <id> --phase review
```

Create/complete the single-image QA report with `candidate_qa.py`. Do not append the full report to the generation prompt. Record rejection using a short failure category:

For new reports, initialization writes schema 2: candidate/contract hashes, review-input fingerprint and observed final-image regions. Target regions remain in `quality_contract.layout`. Query a saved report with `candidate_qa.py ... --status`; a review packet also returns a `review` disposition when the candidate links a report. This is a deterministic validity check, never a model call. `REUSE/PASS` means reuse those observations and await the real human decision; `REUSE/FAIL` means correct/replan, not re-inspect unchanged bytes; uncertainty requires resolving the boundary or human review. Incomplete reports need completion. `INVALIDATED` explains that image, reviewed evidence/context, contract or rule version changed; create a new report and inspect the affected candidate. Do not edit a binding merely to make a stale report pass. Legacy reports remain historical; they lack the new reuse binding.

Use `--comparison-image <package-relative-path>` at report initialization for actual peer images inspected for set continuity. Their bytes participate in validity. A newly added comparison or a changed peer needs a fresh report for that comparison. Progress queries and switching to another child never authorize image regeneration or another visual inspection. Local integrity checks remain active, including final export provenance; this is saved visual-result reuse, not a new persistent cache of every static validation. Reuse currently applies to the whole report, not individual checks: even a local copy/reference change can invalidate that report. Re-inspect the affected candidate under the current binding, without restarting unrelated image tasks or product intake; do not claim per-check caching or silently carry old checks into a new report.

After finishing a report, link it using the existing record command: `set_runtime.py <package> --set-id <set> record --module-id <id> --decision PENDING_REVIEW --report qa/visual/<candidate>.json`. This preserves pending human review and makes the report path/disposition available to later review packets. For a failure, record the appropriate rejection with the same report instead. An unlinked report is not discovered by scanning unrelated QA files; query its known path directly until linked.

The same invalidated/failed input without any corrective change is not progress: retain the result and proceed to its stated next action. Preserve the existing blocked/retry states rather than adding a second phase machine. After an interrupted tool call, reconcile the job/result and both raw/final paths before attempting generation again.

New A+ output requirements also contain `pre_crop_review: OBSERVED_LAYOUT_V1`. The generation/postprocess packet gives `source_review_path`: initialize that existing QA report type with `candidate_qa.py --init --source-image <relative-raw>`, inspect source composition, query `finalize_a_plus_image.py --check-only`, and record the actual reviewed normalized crop plus layout/design observations. Guarded export binds this source report and contract in the PNG. Preserve it; final QA uses a different report path and the final image hash. Unknown/failed source layout cannot be accepted by exporting through the legacy command without a guard. Old contracts without this requirement keep their original workflow until an explicit revision.

```text
python3 scripts/set_runtime.py <package> --set-id <set> record --module-id <id> --decision REJECTED_TOPOLOGY --failure-code HARDWARE_STATE --report qa/visual/<candidate>.json
python3 scripts/set_runtime.py <package> --set-id <set> prepare --module-id <id> --retry --correction "Preserve the original connector count and routing"
```

A retry requires a recorded rejection, keeps the prior candidate/contract, creates a new attempt and carries only one current corrective instruction (at most 300 characters). The correction cannot change approved facts, copy or pose; those need a revised plan. Attempts are bounded to the original plus two retries. After that, replan or obtain the missing evidence. Do not carry the entire failed QA narrative forward.

A user's focused correction request does not require another routine approval of the full plan. AI may create the necessary in-scope revision for the affected task, retaining previous outputs/history and unaffected image pointers. Do not claim automatic cross-revision acceptance reuse. Do not silently change frozen copy/layout with retry. Validation/plan pinning are internal execution steps; human ACCEPTED is a separate real decision. After mandatory Gallery opening-pair approval, keep producing other already authorized unproduced tasks while candidates await review, using next-generation.

Only after an actual human decision:

```text
python3 scripts/set_runtime.py <package> --set-id <set> record --module-id <id> --decision ACCEPTED --report qa/visual/<candidate>.json --human-reviewer <reviewer> --decision-reference <actual-decision-reference>
```

The decision reference identifies the user's/designated reviewer's real message or review record. Never invent it or use the model's own QA pass as human approval. `--candidate-path` may identify an output moved to accepted storage; its hash must still match. Requery `next` after recording. Optional modules can be selected explicitly with `--module-id`.

## Recovery, limits and compatibility

- Image saved but decision not committed: `prepare` discovers it and resumes review.
- Candidate decision committed but set summary not updated: `next`/`sync` rebuilds the summary from product state.
- Approved spec/catalog/source changed: refuse stale production; create a reviewed revision. Accepted history is retained.
- Default output budget: 12,000 UTF-8 bytes and eight reference files per packet. These are configurable engineering limits, not measured optimal context sizes. `--max-bytes` and `--max-images` can be explicitly increased for essential inputs. An oversized packet fails visibly; no hard constraints are silently truncated.
- The script does not launch image generation. If a generation call times out, reconcile the returned job/output before another call; a repeated packet alone cannot prove whether a remote generator has finished.
- Legacy embedded plans/contracts remain readable. Create a new set for normalized storage when revising them; never rewrite immutable accepted artifacts merely to change format.
- The scripts control what gets read or attached next. They cannot remove earlier messages/images from the same chat's context and do not claim model-session isolation. Handoffs to another execution context need only package path, set ID and optional module ID; reread current state there.

For planning, `module --module-id <id>` returns just the chosen row/spec. Generation and inspection instructions are separate packet phases. Audit/detail files remain available for targeted debugging, without being part of normal inter-image handoff.

Grouped A+ sets retain these per-image contracts/states. `next`/`status` additionally report the saved generation mode, compact page counts and the current image's parent/position, with no neighbouring prompts. `handoff` returns the grouped designer manifest with separate image statuses/output pointers; it does not stitch images, upload content or convert drafts into accepted outputs. Read [a-plus-module-layout.md](a-plus-module-layout.md) when planning/revising selected A+ work. New sets carry their resolved deliverable and per-channel quantity policy; there is no implicit A+-only scope. Gallery handoff returns separate main/secondary outputs, and both returns both channels. Page acceptance is derived from required child decisions and does not change the existing set-completion gate. Resume saved plans as-is, including legacy plans without a generation-mode field; new defaults never enlarge an existing queue.

New generation packets include the current image purpose; review packets include `image_intent` and require `content_coverage`. Assess the actual buyer question and parent responsibility in addition to product identity and rendering. Legacy plans without quantity policy preserve their old packets/checks.

New module-language policy packets also bind the current function, required visible content and role-specific expression in `module_language`; review requires `module_role_fit`. Re-establish that responsibility for every image, including later tasks and resumed work. Shared style does not override the current module's job. In adaptive mode, identical devices/treatments/compositions across different responsibilities raise a planning warning for visual review, not an aesthetic score or a blanket ban on reusable layouts.

New design-policy plans pin one catalog and resolve the current `design_recipe`. Adaptive mode carries the input-led composition, per-image visual adjustments and optional reference-element influences; catalog mode carries the selected preset recipe. Both enter generation and review packets without the whole catalog or neighbouring images. Draft changes use `configure_design.py`; accepted sources and history remain immutable. Research sources must be registered before input snapshot/approval, or introduced in a new revision. For pilots, explicitly select the planned pilot IDs to prepare and inspect each candidate, retaining `PENDING_REVIEW` until the grouped human decision; normal `next` may continue to point at the first pending review.


Structure corrections follow the single-image [state-transfer interface](../../product-single-image-generator/references/state-and-contract.md#structure-state-transfer). Apply the evidence-backed semantic delta, then synchronize. Required locks are compared by content/status against each task's pinned snapshot; unrelated version increments alone do not block a task. Changed/unresolved dependencies produce BLOCKED children and require an explicit affected-task revision. `next-generation` skips blocked children and may continue unrelated unproduced work. Candidate/human history remains intact; state updates do not imply visual acceptance or automatically transfer acceptance across revisions.
