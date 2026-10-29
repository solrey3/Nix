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

- `id`, `publisher` (combined four-script identity), exact `artifact` record or
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

## Native implementation and hard gates

`scripts/jukebox_native.py` fixes bravo, account `budchris`, master/app/home paths,
selected system/user profiles and existing manager unit. There is no arbitrary
home/store/host/command override, plugin loader or live-test environment switch.
Internal dependency injection is trusted test code, not a user artifact hook.

The native reader binds git commit/tree and clean app source, resolved profiles
(including a standalone HM profile when present), unit/drop-in/base-file identity,
manager executable/argv/start/invocation identity, known Node threads and allowed
esbuild child ownership, and a descriptor to the expected database. It compares
read-only logical SQLite schema/all tables, state/configuration hashes, M3Us,
scan-error/activity metadata, and MPD/Navidrome unit identities. Unknown mutable
directories, private-file hardlinks, unsafe ancestry or unsupported process shapes
fail closed; nothing is migrated, scanned into the app, deleted or force-killed.
Playlist observation caps are 5,000 namespace entries and 128 MiB aggregate M3Us;
individual metadata/API/command outputs have separate finite bounds.

The actual stop policy must be `SendSIGKILL=no`, `KillMode=control-group` before
eligibility. **Compatibility with installed bravo has not been probed.** A
failure here is a blocker, not permission to change the unit or weaken policy.

Owned subprocesses use fixed trusted tool locations, bounded combined output,
no shell, no kill/retry and mandatory actual-exit drain. Root preparation forbids
package build/substitution fallback and independently queries manifest references
and actual root registration. No GC/purge/profile/build command is exposed.

The localhost API allowlist is only `config`, `scan`, `operations/schedule`,
`discovery`, `discovery/runs` at `127.0.0.1:3080`; only GET is issued. Proxies and
redirects are disabled. Size and total-read deadlines apply. Errors do not expose
headers, credential values, responses or raw helper output.

`scripts/jukebox_cli.py` gates native review/apply/rollback/discard modes behind
`--approve`, an independently hash-pinned private plan and an explicit credential
FD. The FD must be a bounded regular file or EOF-terminated pipe, contain one
24–256 byte printable token with at most one final newline, and meet a five-second
read deadline. No credential comes from argv, environment, other services or
parsing `.env`; `.env` is only privately hashed/backup-verified. Artifact inspection
still cannot construct a home publisher, read credentials, spawn commands or
contact an API. Ungated native modes refuse before home/host/token access.

## Backup contract and remaining live-workflow gaps

Backup creation stays in the **existing Jukebox deployment workflow**, not this
Nix publisher (operator decision in #121). The companion Jukebox source helper
`App/deploy/export_playback_receipt.py` verifies already-prepared private copies
and seals the receipt; it does not create/copy a backup. Review both source changes
together before any use. A future separately approved operation must create a
coherent sealed backup and independently pin its receipt. The
native verifier does not search/choose a convenient backup or trust reported
hashes alone. Fixed destination:
`App/data/deployment-backups/publisher-reviewed-<32-hex-id>/`, private owner-only
directory, with private `receipt.json` and `jukebox.sqlite`, `configuration.env`,
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
