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

## Production loop

All commands below run from this skill's directory and take the existing package path. Use one serial writer per product package; these scripts are not a multi-worker job scheduler.

```text
python3 scripts/set_runtime.py <package> --set-id <set> next
python3 scripts/set_runtime.py <package> --set-id <set> prepare
```

`next` synchronizes decisions and returns counts, one current module and the next action. `status` is a read-only view of last recorded state, augmented by discovery of already-saved outputs. `prepare` materializes only the selected module, activates its run and performs preflight. Repeating it reuses the same contract. If an image exists, it returns a review packet and never overwrites the image.

For already authorized batches where the remaining planned images should be produced before grouped human review, use `next-generation` to select an unproduced ID, then call `prepare --module-id <id>`. This does not accept or discard pending candidates and does not authorize expanding the batch. The usual `next` intentionally prioritizes pending review; never interpret that repeated task as another generation request. In a web workflow without scripts, keep an explicit image-ID/task/status/output ledger and select an unproduced task from it before every call, rather than continuing from the last hero's prompt.

For generation, pass only `prompt` and references whose `kind` is `image` to the image generator. Document pointers remain available for targeted verification; do not submit a PDF/JSON guideline as an image or dump its full text into the prompt. The shared visual system should already contain the needed normalized style decisions. Save at `output_path`. Preserve image roles: original evidence controls identity; pose/style/prior images have their limited roles. Do not attach every earlier image or feed a failed image forward by default.

```text
python3 scripts/set_runtime.py <package> --set-id <set> record --module-id <id> --decision PENDING_REVIEW
python3 scripts/set_runtime.py <package> --set-id <set> packet --module-id <id> --phase review
```

Create/complete the single-image QA report with `candidate_qa.py`. Do not append the full report to the generation prompt. Record rejection using a short failure category:

```text
python3 scripts/set_runtime.py <package> --set-id <set> record --module-id <id> --decision REJECTED_TOPOLOGY --failure-code HARDWARE_STATE --report qa/visual/<candidate>.json
python3 scripts/set_runtime.py <package> --set-id <set> prepare --module-id <id> --retry --correction "Preserve the original connector count and routing"
```

A retry requires a recorded rejection, keeps the prior candidate/contract, creates a new attempt and carries only one current corrective instruction (at most 300 characters). The correction cannot change approved facts, copy or pose; those need a revised plan. Attempts are bounded to the original plus two retries. After that, replan or obtain the missing evidence. Do not carry the entire failed QA narrative forward.

A user's focused correction request does not require another routine approval of the full plan. AI may create the necessary in-scope revision for the affected task, retaining previous outputs/history and unaffected image pointers. Do not claim automatic cross-revision acceptance reuse. Do not silently change frozen copy/layout with retry. Validation/plan pinning are internal execution steps; human ACCEPTED is a separate real decision. Keep producing other already authorized unproduced tasks while candidates await review, using next-generation.

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
