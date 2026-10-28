# Jukebox public playback artifact and isolated publisher core

Source work: [Nix #74](https://github.com/solrey3/Nix/issues/74),
[Jukebox #121](https://github.com/solrey3/Jukebox/issues/121), based on the
[reviewed design](https://github.com/solrey3/Jukebox/blob/f24ebeb79fd46524aa5c7725217b709df4ead00d/App/docs/nix-playback-delivery-design.md).
**Draft implementation; NOT activation-ready. No live mutating adapter is
shipped.** Do not interpret tests, a source PR or artifact evaluation as permission
to install files, register production roots, restart services or run playback.

## Implemented

`jukeboxConfigurations.bravo` is a dedicated data output. It imports only
`lib/jukebox-playback.nix`, whose arguments are the tracked two-file payload,
lockfile and source revision. It uses builtins, not nixpkgs/Home Manager or a
package builder. Selecting it does not select a host, default package, profile,
activation script or deployment output. Existing host/daemon/HM declarations and
flake.lock are unchanged.

`config/jukebox/bravo` has exactly two regular public payloads:

- `playback.env`: one bravo loopback MPD endpoint (6600), Music/ prefix and empty
  Navidrome URL. No password, other zone, stream or permission flag.
- `90-playback.conf`: the existing manager's appended EnvironmentFile directive.

The manifest records schema/account/role/config-home, immutable source revision
(or null for a dirty/review candidate), lock hash, destinations, sizes, digests
and files-directory store path. `builtins.toFile` preserves that path's store
context, so retaining the manifest retains the payload directory. Source and
payload inputs are independently checked; a self-reported revision is not trust.

`scripts/jukebox_playback.py` implements:

- Independently pinned artifact inspection; strict schema/public-value/size/type/
  path/control/digest checks, duplicate/nonfinite JSON refusal, public-safe errors.
  Read-only optimized hardlinks in the pinned immutable Nix store are supported;
  mutable home records/public ownership links still require link count one.
- No-follow directory-relative fixture-home operations, owner/mode/hardlink/
  ancestor guards, no foreign/equal-byte adoption or first-pointer overwrite.
- Private state/retained-root/evidence bounds, recognized entries only, exact
  ownership links/journal agreement, no auto-purge or repair.
- Non-queuing lock; ten-minute boot/UTC/monotonic/source/state/publisher-bound
  one-shot reviews, explicit discard, root uncertainty recorded before helper
  invocation, lock held until actual helper drain. All retained roots are checked.
- Durable consumed intent/pending registry before backup or service effects;
  complete fake apply, same-payload no-op, generation update and explicit rollback
  contracts; any incomplete/ambiguous evidence blocks later mutations.
- Exact manager stop/start/user-daemon-reload request allowlist. Schema 1
  conservatively requires explicit reload scope for each changed generation.
- Explicit record of an independently approved/completed HM ownership handoff;
  exact actual generation links and bytes are required, not merely equal content
  at a foreign link. Transferred ownership refuses later dedicated mutation.

The only command-line mode that can proceed is **artifact inspect**. It does not
construct a home publisher, read credentials/state, contact an API, spawn any
command, register a root or install anything. All other CLI modes fail closed
before accessing a home/manifest. There is no `--force`, arbitrary home/store/
command override, adapter plugin loader or hidden live-test environment flag.
Core dependency injection is an internal trusted Python interface, not a user
supplied script/hook in an artifact.

## Not implemented / necessary before any live workflow

The production evidence/backup/root/process/readiness adapter is **intentionally
absent**, not simulated as successful. Core tests prove orchestration with a
recording fixture adapter, NOT actual systemd, GC-root registration, current
Jukebox resource ownership, complete backup correctness or deployment readiness.
Do not wrap the fixture Fake adapter around real commands or enable CLI mutation.

A separately reviewed adapter must independently verify actual source/profile/
account/runtime/tool/unit/drop-in identity, environment precedence, bounded job/
transaction/worker observations and fresh app-state/SQLite/config backups. Its
snapshot consists only of fixed non-secret digest fields (`profiles`, `flags`,
`source`, `invocation`, `unit`, `resources`, `tools`, `stopPolicy`) plus an explicit
eligibility boolean; its backup reference contains only a bounded ID and digest.
Raw credentials, API responses, paths/private environment values or arbitrary
error payloads may not be journaled. Digests do not authenticate their producer:
the adapter's implementation and independent activation plan need review.

That adapter must prove root reference/registration semantics without package
build/substitution fallback, actual owned-child closure after timeout, normal
manager-only lifecycle, read-only config readiness and immutable-state/flag/profile/
peer preservation. Source/hash/time/service binding and exact live failure policy
(including any containment stop) require a new reviewed plan. No automatic retry,
resume, repair or rollback is permitted. Configuration rollback never restores an
old app database or changes another controller's files.

The core's `record_transfer` only records a separately approved, already completed
handoff after exact link/content proof. It does not unlink dedicated files or run
Home Manager. A full transfer controller and live recovery of blocked transactions
are not shipped; unknown state stays blocked, never force-cleared. Quotas stop
preparation rather than expiring/deleting roots/evidence. No GC command exists.

## Scoped validation (one-time operator exception)

The operator explicitly authorized **one feature-PR exception** to the normal
README/host-settings update validation rule in Jukebox #121: no lock update,
package/system/HM build, full fleet check, Darwin/Echo evaluation or activation.
This is not a change to the standing repository policy. Record omitted wider
checks in the PR, do not claim they pass.

Fixture suite (standard library only):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_jukebox_playback.py -v
```

It uses only owned temporary homes/store/state and Fake evidence/command runners:
no user-systemd, live API authentication/config, real GC roots, MPD/media/provider
or master-library operations. Fault injection covers first install, update and
initial rollback filesystem/journal boundaries, helper actual-exit exclusion,
uncertainty/replay refusal, stale/foreign edits, malformed artifacts, quotas,
explicit transfer and CLI refusal/redaction. It does not validate a live adapter.

Evaluation-only input-isolation fixture:

```sh
nix-instantiate --read-write-mode --option allow-import-from-derivation false --eval --strict --json tests/jukebox-artifact.nix
```

Every package/fleet flake input in that fixture is a throwing value. The public
output must still evaluate; the fixture revision is synthetic, not deployment
identity. `--read-write-mode` is required for `nix-instantiate --eval` to actually
materialize the plain public store objects rather than only calculate paths.
Only approved public immutable store artifacts are materialized; no derivations
are built and no GC roots are registered.

A focused immutable source-revision check may evaluate only the dedicated output
with `--no-update-lock-file` and IFD disabled, then use `nix-store --query
--references` on its manifest to verify the payload reference. This is not a
profile or GC-root operation and does not build a package. Never use the fixture
manifest as proof of an approved real source. Dirty-source manifests are
inspection candidates, not acceptable production identities.

Do not run `scripts/check-updates`, `nix build`, `nix develop`, `nix flake check`,
GC, profile/activation commands or production publisher modes as part of this
scoped validation. Actual production preparation/installation requires a later
explicit approval; neither app deployment #117 nor design #119 authorizes it.
