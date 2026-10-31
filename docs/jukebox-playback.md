# Jukebox public playback artifact and guarded publisher

Source work: [Nix #74](https://github.com/solrey3/Nix/issues/74),
[Jukebox #121](https://github.com/solrey3/Jukebox/issues/121), based on the
[reviewed design](https://github.com/solrey3/Jukebox/blob/f24ebeb79fd46524aa5c7725217b709df4ead00d/App/docs/nix-playback-delivery-design.md).
**Draft source implementation; NOT activation-ready.** Native evidence/lifecycle
code is shipped behind independent plan/approval/credential gates, but has only
been exercised against fixtures. Tests, source review and artifact evaluation
are not permission to use production publisher modes or prepare a live window.

## Public artifact

`jukeboxConfigurations.bravo` imports only `lib/jukebox-playback.nix` and tracked
payload/lock/revision data. Builtins create plain public store objects; no
nixpkgs, Home Manager, host/default package, profile or builder is selected.
Host/daemon/HM declarations and `flake.lock` are unchanged.

`config/jukebox/bravo` has exactly two public files:

- `playback.env`: bravo loopback MPD port 6600, `Music/` prefix, empty Navidrome URL.
  No password, other zone, stream or permission flag.
- `90-playback.conf`: the existing manager's appended EnvironmentFile directive.

The manifest binds schema/account/role/config-home, immutable source revision
(null for a dirty candidate), lock hash, destinations, sizes, hashes and payload
store directory. `builtins.toFile` retains the manifest-to-payload store reference.
Self-reported revision/hash values do not replace independent approval pins.

## Publisher core

`scripts/jukebox_playback.py` implements strict pinned inspection, bounded JSON/
public values, immutable-store optimized hardlink support, directory-relative
no-follow mutable-home operations, ownership/mode/link/ancestor checks, and refusal
to adopt foreign/equal-byte/half-pair paths. Private journals, retained roots and
recognized evidence are bounded; nothing is auto-purged or repaired.

A non-queuing lock protects boot/UTC/monotonic/source/state/publisher-bound one-shot
reviews. Native reviews also bind the exact independent activation-plan digest.
Root uncertainty is recorded before helper invocation; owned helpers must actually
exit before lock release, including on errors. Consumed intent/pending state is
synced before backup or lifecycle effects. Incomplete/ambiguous evidence blocks
later mutation. Root/reference proof is independent of an existing equal link.

Apply supports first install, same-payload no-op, generation update and separately
reviewed manual configuration rollback. A no-op preserves the prior rollback
target. Stable owned links use one current pointer, not a filesystem-wide atomic
transaction. Changed generations explicitly request user-manager-wide daemon
reload and normal manager-only stop/start; no other unit is acted on.

The core can record an independently approved/completed HM handoff only after
actual generation links and bytes are proven. Equal foreign bytes are not proof.
It does not run HM, unlink for transfer or restore an old database.

## Approved evidence policy: coordinated operator window, not a lease

The operator approved this policy for **source and fixture work only** in #121.
A future activation must explicitly coordinate a window preventing concurrent
Jukebox clients/mutations and external configuration, library, device, profile or
service edits. This is an operator assumption, **not an atomic app admission
lease, global-idle proof or exclusion of every external process**. The app has no
external atomic maintenance fence. Polling cannot close that race.

`scripts/jukebox_window.py` requires a strict independently hash-pinned private
activation plan. Schema 1 includes:

- `id`, `publisher` (combined five-script identity, including `jukebox_backup.py`), exact `artifact` record or
  null for rollback to absence, and `backup` containing an exact receipt ID/hash;
- literal `window=operator-coordinated-no-concurrent-clients-or-external-edits-v1` and
  `failurePolicy=manual-block-no-retry-resume-rollback-or-containment-stop-v1`;
- explicit true `allowPreparation`, `allowManagerStopStart`, and
  `allowUserDaemonReload` permissions (including preparation effects during review);
- `bootId`, `createdUtc`, `createdMonotonic`, `expiresUtc`, `expiresMonotonic`:
  consistent same-boot UTC/monotonic bounds, at most 600 seconds;
- `expected`: independent digests for `profiles`, `flags`, `source`, `invocation`,
  `unit`, `resources`, `tools`, `stopPolicy`.

These digest fields are not authenticated facts merely because they look like
hashes. Source and producer review plus independently obtained observations and
specific activation approval remain necessary. The same exact plan is required
for review and apply; a renewed/substituted plan cannot consume an old review.
There is no self-approval, plan generator or activation approval in this PR.

Bounded pre-stop observations require idle scan/discovery/scheduler states,
recognized completed import/download records, no observable active transaction,
expected indexed count and known process/worker ownership. Stopped-state checks
require prior owned process exit (handling PID reuse), inactive/dead successful
unit, an empty prior cgroup, and preserved immutable resource/profile/flag/peer
observations. Readiness checks require the expected server-reported zone mapping,
Navidrome off and unchanged permission/scheduling state. They are local config
readiness, **not MPD connectivity/index coverage/audio or private HTTPS proof**.

## Stable scheduler observation contract (Jukebox #125)

The actual app's schedule response has a fresh `capturedAt` on every read. With
an empty schedule table it also creates process-local `revision` and `last.at`
values at startup. Hashing/comparing the whole DTO rejected safe repeated reads
and restarts; constant-response fixtures had hidden that fail-closed mismatch.

Native IO now reads scheduler **schema and bounded rows in the same read-only
SQLite transaction as all logical dataset hashes**. A table count, API claim,
cached default or missing table is not absence proof. Require the exact current
`collector_schedule_v1` table SQL/columns/constraints, no unknown triggers, at
most one KEXP row, bounded duplicate-free JSON, the physical root and strict
current disabled-state shape. Missing/weakened/unknown schema, malformed/foreign
rows, API/database disagreement, unavailable/blocked/busy/capability-enabled
status or unknown DTO fields refuse. This witness is trusted internal IO output,
not a new app API, caller plan field or self-asserted HTTP proof.

The private stable projection validates and omits only retrieval `capturedAt`.
For a proven empty table **and exact unconfigured API defaults**, it additionally
omits only process-local `revision` and `last.at`, labels storage `empty`, and
retains the other defaults explicitly. It never writes a fake empty definition
or fabricates durable identity. For stored disabled rows, label storage `stored`
and retain **every state field**, including revision, last time/outcome/slot/run,
definition, rights, failures and watermark. They must match the actual stored row.
Full raw table hashes/schema remain bound into private resources and the sealed
backup, so row presence, byte-level storage or durable-field changes still
invalidate review. Source/publisher/plan/boot/time/flag/worker/root gates are
unchanged; previous plan pins are not reusable after this source change.

Fixtures now use realistic changing retrieval times and empty-state startup IDs,
exercise stored/history restart stability and genuine drift refusal before
service actions or at post-start verification without retry/rollback. A separate
cross-source check runs the **actual CollectorScheduler class** with owned
synthetic SQLite databases, timers off and throwing collector/work callbacks;
its empty/stored/history responses and schema satisfy this contract. No production
scheduler, state, credential, API or service is used. These observations still do
not create atomic admission against external clients: the approved coordinated
operator window and full resource rechecks remain necessary.

## Native implementation and hard gates

`scripts/jukebox_native.py` fixes bravo, account `budchris`, home, physical master
`/mnt/files2/Jukebox`, and the separated project `/home/budchris/Projects/Jukebox`
from Jukebox #123. App/data and Telemetry/JukeboxApp are under that project,
not the media root. Git source identity uses the project; master M3Us use the
physical root, never the project's navigation symlinks. Storage paths join the
source digest and require new independently pinned observations/receipts/plans
following relocation. Unit WorkingDirectory and actual process cwd must match
that App directory. Selected system/user profiles and the existing manager unit
remain fixed. There is no arbitrary
home/store/host/command override, plugin loader or live-test environment switch.
Internal dependency injection is trusted test code, not a user artifact hook.

The native reader binds git commit/tree and clean app source, resolved profiles
(including a standalone HM profile when present), unit/drop-in/base-file identity,
manager executable/argv/start/invocation identity, known Node threads and allowed
esbuild child ownership, and a descriptor to the expected database. It compares
read-only logical SQLite schema/all tables plus same-transaction scheduler storage
evidence, state/configuration hashes, M3Us, scan-error/activity metadata, and
MPD/Navidrome unit identities. Unknown mutable
directories, private-file hardlinks, unsafe ancestry or unsupported process shapes
fail closed; nothing is migrated, scanned into the app, deleted or force-killed.
Playlist observation caps are 5,000 namespace entries and 128 MiB aggregate M3Us;
individual metadata/API/command outputs have separate finite bounds.

### Whole-group ownership and closure (Jukebox #126)

Manager ownership checks read the child list of **every bounded known Node
thread**, not just the main thread. The only optional child is the expected
esbuild executable/arguments; all of its bounded thread child lists must be
empty, including descendants that might have left the unit's group. Active
cgroup membership must be exactly the manager plus that known compiler. Main
and compiler start identities are rechecked; cgroup identity/members/child starts
join the invocation digest. Unexpected owners cannot be accepted merely because
unit status/API flags look idle.

Cgroup-v2 reads are bounded and directory-descriptor anchored, no-follow and
read-only. Require consistent `cgroup.procs` and `cgroup.events` (`populated`,
`frozen`) across reads, a bounded unchanged regular-file namespace and the same
named group identity. Unknown subgroups (even empty), links/nonregular nodes,
foreign members, duplicates/malformed/oversized/changed evidence or frozen state
refuse. Delegated/subgroup layouts are not adopted or recursively acted upon.

After normal stop, first prove the prior owned PID exited (different start time
handles PID reuse). A still-present group must have its previously observed
identity, no members/subgroups and population=0/unfrozen. A removed group is
absence only after explicit ENOENT below accessible anchored cgroup ancestry;
missing/unavailable mounts, PID stat files, metadata fields or permission errors
are NOT closure. No process/cgroup is killed, moved, emptied, repaired or
removed by these readers. Tests use virtual proc/cgroup trees only; actual bravo
layout/access remains a separate compatibility gate. These repeated checks do
not replace the coordinated operator window with global atomic exclusion.

The actual stop policy must be `SendSIGKILL=no`, `KillMode=control-group` before
eligibility. **Compatibility with installed bravo has not been probed.** A
failure here is a blocker, not permission to change the unit or weaken policy.

Under explicit #131 approval, the separately tracked manager-only
`80-stop-safety.conf` may be loaded alongside the canonical playback drop-in.
It must be a private, single-link, no-follow regular file containing exactly
`[Service]` and `SendSIGKILL=no` with final newlines. Its filesystem identity and
content digest join the base-unit evidence; it is not an arbitrary drop-in
allowance. Duplicate, foreign, missing, unloaded, unsafe or modified safety files
refuse. Initial empty playback may include this safety file, but no playback
configuration. Publication and rollback preserve it; no policy installation,
profile activation or new service action is added to the publisher.

Owned subprocesses use fixed trusted tool locations, bounded combined output,
no shell, no kill/retry and mandatory actual-exit drain. Root preparation forbids
package build/substitution fallback and independently queries manifest references
and actual root registration. No GC/purge/profile/build command is exposed.

The localhost API allowlist is only `config`, `scan`, `operations/schedule`,
`discovery`, `discovery/runs` at `127.0.0.1:3080`; only GET is issued. Proxies and
redirects are disabled. Size and total-read deadlines apply. Errors do not expose
headers, credential values, responses or raw helper output.

`scripts/jukebox_cli.py` gates mutating native review/apply/rollback/discard modes behind
`--approve`, an independently hash-pinned private plan and an explicit credential
FD. The FD must be a bounded regular file or EOF-terminated pipe, contain one
24–256 byte printable token with at most one final newline, and meet a five-second
read deadline. No credential comes from argv, environment, other services or
parsing `.env`; `.env` is only privately hashed/backup-verified. Artifact inspection
still cannot construct a home publisher, read credentials, spawn commands or
contact an API. Ungated native modes refuse before home/host/token access.

## Read-only retained-evidence inspection (Jukebox #127)

`inspect` remains public artifact inspection: no home/credential/helper access.
The distinct `inspect-state` source interface requires explicit **read-only**
`--approve` and an independently supplied matching `--expected-publisher-sha256`
before host/home/state access. It refuses manifest, activation-plan, review-ID
and credential-FD arguments. The read-only pin is rejected by mutable modes;
their private plan/credential/window gates are unchanged. Source publication
is NOT approval to invoke either native interface against live state.

The evidence inspector only reads the dedicated publisher namespace and lstat
metadata for the two public targets. It opens an **existing** private lock
read-only and takes a non-queuing shared lock, never creating state or a lock.
Missing, busy, unsafe, unavailable, changed and unknown coverage is explicit;
unknown inventory totals are null rather than invented zero. A one-shot report
has bounded structural registry/review/transaction enums, derived inert reference
hashes (not raw action IDs), link counts and observed pending-name counts. Limits:
128 entries per directory, 64 KiB per committed record, 20 MiB total read budget,
50 rows per namespace with explicit omissions/unknown-record coverage. Unknown
names/values/payloads/errors/paths are not echoed. Known pending payloads are
never read, interpreted or cleaned up.

No artifact/root/public link target is followed and no source record can select
a file outside this namespace. No adapter, command, API, process/profile/store
query, credential, app configuration, library or backup read occurs. Every
report, including `observed` or `absent`, has writes/actionable/activationAuthorized/
recoveryAuthorized **false**. It is structural evidence only: ownership, root
registration, artifact bytes, deep bindings/cross-record consistency, readiness
and backup correctness are explicitly **not checked**. Metadata identity rechecks
can mark a view changed; they are not an atomic/global-idle proof.

The reporter can describe retained blocked/incomplete/transferred metadata where
strict mutation admission refuses. It does **not** relax `_registry`, discard a
consumed/blocked review, clear intent, adopt ownership or provide a recovery,
rollback, retry/resume, purge or HM transfer controller. No report authorizes an
action or should be fed into apply. Actual state inspection itself remains a
separately approved production read with the exact source pin; it was exercised
only against owned temporary homes in this source task.

## Backup contract and remaining live-workflow gaps

Backup creation stays in the **existing Jukebox deployment workflow**, not this
Nix publisher (operator decision in #121). The companion Jukebox source helper
`App/deploy/export_playback_receipt.py` verifies already-prepared private copies
and seals the receipt; it does not create/copy a backup. Review both source changes
together before any use. A future separately approved operation must create a
coherent sealed backup and independently pin its receipt. The
native verifier does not search/choose a convenient backup or trust reported
hashes alone. Fixed destination:
`/home/budchris/Projects/Jukebox/App/data/deployment-backups/publisher-reviewed-<32-hex-id>/`,
private owner-only directory, with private `receipt.json` and `jukebox.sqlite`, `configuration.env`,
`app-files/` copies, and `telemetry-metadata/` copies.

Receipt schema is exactly `{schema: 1, dataset: ...}`; the dataset must equal the
fresh native observation. Actual copied SQLite schema/rows, configuration and
recognized state/telemetry bytes are read and independently compared. M3Us are
hashed/preserved in place, not rewritten or represented as a full media backup.
The receipt hash and ID are independently plan-bound; historical backups remain
untouched. Unknown/missing/stale copies refuse before service actions. Exporter
uncertainty markers `.receipt-export-intent.json` and `.receipt-pending` refuse;
retained `export.json`, when present, must bind that exact receipt/dataset. The
exporter refuses existing output rather than resuming; a failed export needs
separate inspection, never deletion/retry to appear complete.

`scripts/jukebox_backup.py` checks the **exact** bounded bundle namespace before
any SQLite open, including a second check after receipt reads. Unknown root or
nested files/directories, WAL/SHM/journal sidecars (even empty), missing copies,
uncertainty markers, symlinks/FIFOs/hardlinks and unsafe ownership/modes refuse.
Only the two recognized metadata directory trees, exact dataset-named files,
receipt and optional completion proof are allowed; empty recognized directories
are permitted, not arbitrary extra directories. No rejected evidence is removed.

All ancestry/child opens are directory-descriptor relative and no-follow. File
and directory device/inode/mode/owner/link/size/mtime/ctime snapshots are compared
around reads and again at successful verification exit, including the named root.
The offline reader opens only its checked descriptor via `/proc/self/fd` with
`mode=ro&immutable=1`, an 8 GiB file bound and 60-second SQLite progress/row deadline.
Other copied metadata is bounded to 512 MiB aggregate / 30,000 namespace nodes,
with individual file limits. It does not consume/create SQLite sidecars, checkpoint,
copy, flush or rewrite evidence. Live WAL observation keeps its existing `mode=ro`
transport; only logical row encoding is shared. Fixture coverage distinguishes
committed live WAL reads from refused sealed WAL copies. Rechecks reduce stale
inputs but do not make external edits globally atomic or replace the coordinated
operator window.

The fifth implementation file changes the publisher identity; old four-script
plans cannot be reused. The migration's historical backup aliases remain the
app's Recovery concern, not a publisher backup search, evidence rewrite or grant
to inspect/reuse historical backups. Actual fresh backup preparation still needs
separate approval.

The failure policy is **manual blocking only**: no automatic retry, resume,
repair, rollback, containment stop or helper killing. A failure can leave the
manager stopped or running changed configuration; retained intent/evidence must
be inspected under a new explicit recovery approval. Readiness GET polling is
bounded and is not a service retry. Never bypass blocked state by deleting files.
Expired reviews require explicit discard under a fresh approved native window;
consumed/uncertain transactions cannot be discarded into apparent success.

Full live HM transfer and blocked-transaction recovery controllers are absent;
CLI transfer refuses. Actual separately approved deployment-workflow backup preparation, live admission/compatibility,
source/artifact/root semantics on bravo, ownership/config precedence and exact
activation/recovery procedure still need separate review and operator approval.
Fixtures are not deployment evidence. No merge or live action is authorized here.

The [proposed recovery/transfer contract](jukebox-recovery-transfer-contract.md)
(#128) separates a bounded baseline from any future blocked-admission release or
ownership rebinding. It documents missing proof/legacy limitations and the policy
choice required before writing controllers. It is design only, not an accepted
schema, admission exemption, live procedure or implementation approval extension.
Quarantine/manual blocking remains the default.

## Scoped validation (one-time operator exception)

The operator authorized **one feature-PR exception** to README/host-settings update
validation: no lock update, package/system/HM build, full fleet check, Darwin/Echo
evaluation or activation. Standing repository policy is unchanged; omitted wider
checks must be disclosed, not claimed as passing.

Fixture suite (standard library only):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_jukebox*.py' -v
```

Owned temporary homes/stores/SQLite/proc/cgroup/profile/unit trees, fake API/tool
transports and synthetic credential FDs cover native-reader/CLI flows as well as
core orchestration. Small owned helper children test timeout/drain, never kill.
Fault injection covers install/update/rollback filesystem/journal boundaries.
No actual systemd/API authentication, production GC roots, library/provider/MPD
commands or production credentials are used. Native production behavior remains
unproven.

Evaluation-only isolation fixture:

```sh
nix-instantiate --read-write-mode --option allow-import-from-derivation false --eval --strict --json tests/jukebox-artifact.nix
```

Unrelated flake inputs throw. The revision is synthetic, never deployment proof.
`--read-write-mode` materializes only approved public plain store objects; no
builder or GC root is involved. A focused committed-source leaf check may evaluate
only this output with IFD disabled/no lock updates and query manifest references.
Dirty/fixture artifacts are not acceptable production identities.

Do not run `scripts/check-updates`, `nix build`, `nix develop`, `nix flake check`,
GC/profile/activation commands or production publisher modes for this scoped
validation. App deployment #117, design #119, implementation approval #121 and the
window-policy decision do not authorize actual preparation or activation.
