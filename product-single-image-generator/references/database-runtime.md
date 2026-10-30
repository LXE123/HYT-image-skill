# Project database and image review

Local projects use one `PROJECT.sqlite3` as the authority for production data across the three sibling skills. Install the three skills together; the shared implementation is `product-single-image-generator/scripts/project_store.py`. Python's standard-library `sqlite3` is sufficient. No server, ORM, network lock, heartbeat or background worker is required.

Images, original evidence, `index.json`, commercial source registrations and local identity-anchor/geometry assets remain files. Plans, per-image specifications, pinned input snapshots/catalogs, contracts, visual-QA records, product facts/locks, runs, candidates, decisions and module progress live in the database. Do not maintain matching live JSON copies. Markdown describes rules; it is not the project progress ledger. Human review remains a decision about the actual image.

## Addresses and queries

Names such as `PRODUCT_STATE.json`, `visual_sets/<set>/SET_PLAN.json`, `visual_sets/<set>/modules/<id>.json`, `runs/<run>/<view>_generation_contract.json` and `qa/visual/<candidate>.json` are stable **database record addresses**, retained in command parameters and bindings. They are not paths to open/edit with filesystem tools. `*_path` fields referring to these records contain addresses; reference-image/output paths still identify actual files. Existing JSON schema examples describe query results.

Run the following from the single-image skill directory. For routine set execution, prefer the Amazon runtime's smaller `status`, `next`, `module`, `packet` and `handoff` results.

```text
python3 scripts/project_records.py <package> list
python3 scripts/project_records.py <package> get --address PRODUCT_STATE.json
python3 scripts/project_records.py <package> get --address visual_sets/<set>/modules/<id>.json
```

The database stores product metadata, individual locks/runs/candidates/decisions, sets/modules, addressed planning/review records and generation claims. Set summaries are derived from sets; there is no separately writable product summary. Status indexes support queue queries. JSON payloads retain flexible creative/evidence fields without adding a column for each product-specific idea.

## Fill a draft, then execute

AI authors evidence-backed facts and creative choices. Database storage does not invent them. To fill an initialized draft, export just that record to a temporary JSON outside the production namespace, edit it, then import it. `get --output` returns its current record SHA-256; pass that value to `put` so an older draft cannot replace a newer record.

```text
python3 scripts/project_records.py <package> get --address <address> --output <temporary-draft.json>
python3 scripts/project_records.py <package> put --address <address> --input <temporary-draft.json> --expected-sha <returned-sha>
```

Draft edits cannot replace execution progress, candidate decisions or pinned catalogs/snapshots. Approved plans require a new set revision. Established structure locks use `revise_structure_state.py`; candidates already claimed/produced require a new attempt rather than editing their contract. QA drafts are filled only after inspecting the actual pixels; stored observations are not automatic visual acceptance. Preserve finalized reports and use a new report address for a subsequent inspection. Record human decisions through `set_runtime.py record` or standalone `record_candidate.py`, with the actual reviewer/message and linked QA.

## Short transactions and external generation

Every state-changing command reads current records under `BEGIN IMMEDIATE`, then commits related database writes together or rolls them back together. Candidate decisions and their derived set/module statuses share one transaction. Image processing and external image-generation calls do not hold the database write lock. File output is outside the database transaction and is preserved on a registration failure.

For set production, `prepare` creates/resolves a contract and previews the current work; it does not reserve an external generation. Before each new image-tool call, claim that exact module:

```text
python3 scripts/set_runtime.py <package> --set-id <set> claim --module-id <id>
```

Run this command from the Amazon skill directory. It rechecks the current task and commits its claim before returning a prompt, references, output path and `claim_token`. Call the image tool once with that claimed packet. Keep the token through image save/registration:

```text
python3 scripts/set_runtime.py <package> --set-id <set> record --module-id <id> --decision PENDING_REVIEW --claim-token <token>
```

An active claim is `GENERATING`, cannot be claimed again and is excluded from `next-generation`. The claim is an execution record; it is not a long database lock or human approval. Other authorized modules may proceed serially while images await review, subject to the existing Gallery opening-pair gate.

Standalone work uses `validate_run_records.py ... --ready-for-generation --claim` after filling/compiling the draft. It returns a claim token. Save the image, then use `record_candidate.py <package> --contract <address> --decision PENDING_REVIEW --claim-token <token>`. Human acceptance uses that command with `--decision ACCEPTED --report <address> --human-reviewer <actual-reviewer> --decision-reference <actual-message>`. Set-linked decisions must go through the set runtime so their module statuses commit together.

## Interrupted calls

Query the saved attempt and inspect both raw/final output paths. Do not infer that a remote generation failed merely because the chat timed out. `list` includes active claim tokens for resuming the local project.

After establishing the actual outcome, run:

```text
python3 scripts/set_runtime.py <package> --set-id <set> recover --module-id <id> --claim-token <token> --reason <actual-outcome>
```

An existing final resumes inspection; an existing A+ raw resumes postprocessing. Neither is regenerated or automatically accepted. With no output and a confirmed failed/abandoned call, recovery records `REJECTED_TOOL`/`TOOL_ERROR` and preserves the attempt. A set retry uses the existing explicit `prepare --retry --correction` route with a new candidate ID, within the original retry budget. Standalone recovery uses `project_records.py <package> recover --address <contract> --claim-token <token> --reason <actual-outcome>`; a replacement uses a new run ID. Tool failure is distinct from visual rejection.

## Legacy projects and exports

An old JSON project must be explicitly migrated once:

```text
python3 scripts/project_records.py <package> migrate
```

Migration imports production JSON in one transaction and retains exact bytes for pinned plans, specifications, snapshots, contracts and visual reports. It normalizes runtime state, then archives original JSON under `legacy_runtime/`; original images/evidence stay in place. New runtime reads never fall back to archived or stray JSON. A malformed import rolls back and leaves the originals usable. An existing database is never merged with a second state source. Migration changes storage only: it does not enlarge a saved queue, grant approval or regenerate an image.

For debugging/handoff snapshots, `project_records.py <package> export --output <new-external-directory>` writes a consistent JSON export. It is a read-only snapshot, not another live project. To move a live project, preserve its database and all referenced images/evidence together after commands have finished. No database or product data belongs in the skill installation package.

## Runtime diagnostics

Project commands append diagnostic events to `runtime/logs/YYYY-MM-DD.jsonl` using UTC dates/timestamps. These files are independent of SQLite: rollback and connection errors remain inspectable even when database access fails. They are diagnostics, not another source of workflow state. Read-only business queries may append diagnostics while leaving product data unchanged. Logs are split by day and retained; there is no automatic deletion policy.

Events identify the command/action, operation ID, parent operation, PID and supplied set/module/run/contract IDs. Transactions have their own ID and requested/started/committed/rolled-back outcome, duration and error traceback. Validation/QA failures, generation claims/results and subprocess exit codes have explicit events. Record-write events inside an ultimately rolled-back transaction do not mean the data committed. A started operation/transaction with no finish event may indicate an interrupted process; inspect its database state and actual images before recovery.

Failure stderr includes the operation ID and log path; normal stdout remains the existing JSON/text protocol. Query from the single-image skill directory:

```text
python3 scripts/runtime_log.py <package> --last 50
python3 scripts/runtime_log.py <package> --level ERROR --last 20
python3 scripts/runtime_log.py <package> --operation-id <id>
python3 scripts/runtime_log.py <package> --set-id <set> --module-id <image-id>
```

For a child failure, follow its `parent_operation_id` and the parent's subprocess events. The query works without opening the database and reports malformed/partial log lines while retaining readable events. Logs omit full argv, prompts/copy, image data, SQL payloads and environment dumps; supplied claim tokens are redacted from errors and captured stderr. Log-write failure emits a stderr diagnostic without undoing a successful business operation or replacing its original exception. Preserve relevant logs with the project when investigating an error.

The runtime does not invoke the external image tool itself. Its internal network/model errors are only known when supplied through the existing registration/recovery commands; put the actual failed/abandoned outcome in `recover --reason`, rather than inferring failure from a timeout. Logs help locate and reproduce a problem; they never auto-retry, change product facts or grant visual acceptance.
