# Proposed recovery and ownership-transfer contract

Design/source review [Jukebox #128](https://github.com/solrey3/Jukebox/issues/128),
under [Jukebox #121](https://github.com/solrey3/Jukebox/issues/121) /
[Nix #74](https://github.com/solrey3/Nix/issues/74). Complements the
[current source implementation](jukebox-playback.md) and
[original accepted design](https://github.com/solrey3/Jukebox/blob/f24ebeb79fd46524aa5c7725217b709df4ead00d/App/docs/nix-playback-delivery-design.md).

**Proposal only. No new controller, policy acceptance, source merge or production
operation is delivered by this document.** Existing implementation/test/window/
backup-producer approvals remain granted; they do not decide how blocked admission
may be released or ownership rebound. Default remains quarantine/manual blocking.

## 1. Distinct capabilities and current code

| Capability | Current source | Meaning / non-authority |
| --- | --- | --- |
| Public artifact inspection | `jukebox_playback.py` / `Artifact` | Independently pinned public payload; no home/state/credential access |
| Local evidence inspection | `EvidenceInspector`, `inspect-state` | Bounded structural metadata only; explicit readonly code pin/approval; no action or recovery authority |
| Normal publication / verified rollback | `Publisher.review/apply`, native window adapter | Fresh one-shot private plan/backup/resource/ownership proof; only known still-owned targets |
| Record an already completed external HM handoff | `Publisher.record_transfer` | Core fixture contract verifies exact chosen-generation links and bytes; native transfer still refuses |
| Orchestrate external HM ownership handoff | Absent | No profile builder/switch or public-link transition controller is shipped |
| Release blocked/uncertain admission | Absent | No completion/resolution ledger, incident proof producer or release controller is shipped |

The inspector's `observed`, `incomplete` and `absent` are not permissions or
proof that an incident is resolved. It deliberately does not validate root
registration, artifact bytes, deep bindings, cross-record consistency, process
closure, profile/service/readiness or backup correctness. Derived report
references are not action IDs. A successful inspection cannot clear anything.

## 2. Failure classification: evidence, not phase-name inference

Current code writes intent before effects, consumes a review before backup/service
actions, retains roots/evidence, and leaves failed work blocking. This is a useful
failure barrier, not a complete post-crash effect ledger:

- `phase = blocked` does not preserve a general last-completed-step history.
  Do not infer that stop, pointer replacement, reload or start never happened.
- `OwnedRunner.pending` and actual-exit drain are in-memory guarantees while the
  owner survives. Current records are not a general durable helper PID/start/exit
  receipt. A crash cannot be backfilled into proof of helper closure.
- A receipt ID/hash is not proof of actual backups without re-verifying the
  independently selected private copies and current resources.
- Restoring equal payload bytes or recreating a link does not restore its old
  inode/ctime/ownership snapshot. Old ownership must not be declared healthy just
  because a manual repair looks equivalent.
- Publication and rollback are configuration-only. Never restore an old app DB,
  discovery state, MP3 or playlist to make an old plan's hashes agree.

| Observed case | Present default | What a future contract would additionally require |
| --- | --- | --- |
| Healthy unused pending review | Existing explicit discard under a fresh eligible window | No extension to consumed/blocked reviews |
| Failed/ambiguous preparation or helper | Quarantine; do not discard blocked evidence | Exact intent/source provenance, actual helper closure and root/effect proof; absence of a receipt is not negative evidence |
| Claimed pre-publication or no-op failure | Quarantine, not a special exemption | Independently establish no relevant external effect, unchanged exact ownership, closed helpers and a separately authorized resolution policy |
| Pointer/reload/start may have occurred | Quarantine; inspect externally only under fresh approval | Actual current links, invocation/closure, effective config, resources and backups; no replay or automatic containment |
| Foreign/partial/equal-byte-new-identity targets | Refuse ownership/adoption | Separately authorized ownership-transfer/rebinding design, not ordinary recovery |
| Broken/unknown schema, missing roots, stale or unavailable proof | Quarantine | No guessing, migration, deletion or phase/status relabelling |
| Completed independently proved HM handoff | Terminal transferred owner after reviewed recording | No reverse transfer or dedicated reactivation by reset |

An operator may later approve a specific manual intervention, but that approval
must identify its real effects. Neither this table nor existing source authority
is that approval. A future controller must distinguish validated evidence from an
operator assumption and fail closed when required provenance is unavailable.
Legacy unknowns do not become eligible merely because new code has been installed.

## 3. Completion-scope / resolution-policy decision

Choose on #128 before writing an admission-release controller:

**A — recommended bounded baseline.** Accept the source delivery as initial
publication, verified still-owned rollback, and inert readonly evidence reporting.
Keep uncertain states quarantined; defer recovery-release and native HM handoff
controllers as explicitly unfinished follow-ups. This does not merge the drafts,
prove installed compatibility or authorize even a readonly live invocation.
Parent #14 and production setup remain partial; do not claim a complete lifecycle.

**B — target a separately reviewed restricted completion policy.** Authorize source
implementation planning for a completion-only admission path, with all of these
conditions; not a general repair or permission to invoke it:

1. A new mode/review/intent class, independently pinned current source/publisher,
   account/boot/time/window, exact incident/journal hashes and actual helper,
   ownership/resource/backup evidence. No old review replay, self-approval or
   conversion of an inspector report into proof.
2. An exclusive non-queuing existing-owner lock, bounded no-follow evidence reads
   and immediate identity/namespace rechecks. No missing/malformed/foreign state
   initializes into apparent success.
3. Only positively proved incidents with unchanged exact dedicated ownership and
   no unresolved relevant external effect may qualify. In particular, post-write,
   changed-link-identity, helper-unknown or legacy missing-proof cases stay blocked.
   If a valid proof producer does not exist, the implementation is incomplete;
   do not invent a receipt or silently add a broad scanner/backup writer.
4. A proposed append-only resolution record binds original evidence, fresh proof,
   approval and outcome. Originals remain consumed/blocked and retained, never
   rewritten as verified/discarded. A separately reviewed registry CAS/validator
   extension would be necessary to acknowledge only that exact resolution; it is
   **not currently authorized or implemented**. No generic nonterminal exemption.
5. The completion path must not stop/start/reload, change public links/pointers,
   rebuild/switch profiles, restore app/media data, adopt new ownership, delete
   roots/evidence, relax quotas or perform the failed action again. Any separately
   approved external intervention is a separate incident plan, not a callback.
6. Failure while recording completion remains blocking. Restart does not resume;
   a new explicit review would be needed, and unknown outcomes remain unknown.
   A later ordinary publication requires a fresh independent ordinary review.

Before implementation, B still needs exact version/schema and proof-producer
contracts, including compatibility with old fail-closed readers and a full crash
matrix. No field names, transition or record format here are an accepted schema.
The decision concerns blocked-admission semantics and delivery scope, **not**
reapproval of existing implementation, validation exception, producer ownership
or operator-window policy. Nothing here permits foreign/equal-byte adoption.

## 4. Future HM handoff: a different transaction

This source proposal does not execute Home Manager, NixOS, `sd-switch`, package
builds or profile activation. Source/installed profile alignment and effects of
any external activation need their own reviewed scope. Do not quietly pin/rewind
inputs or use a subset activation hook as a two-file workaround.

A future handoff contract needs at least these explicit stages:

1. **Fresh handoff review**: exact existing dedicated registry, target/parent/link
   identities, retained roots/artifact, current system/HM profiles, approved chosen
   future generation/source, manager settings/flags, backups and failure policy.
   Ordinary publication's unchanged-profile predicate cannot simply be bypassed.
2. **Durable handoff intent before external effects**: dedicated publication and
   rollback must refuse throughout the handoff. No interval where both controllers
   are allowed to replace the public files.
3. **Separately approved external work**: only its reviewed owner may remove exact
   dedicated links and perform any aligned HM activation. This is not delegated to
   a manifest command or inferred from source approval. Missing/foreign/equal-byte
   targets are not adopted. No automatic retry, rollback or profile switch.
4. **Fresh independent completion proof**: actual public links must identify the
   selected HM generation and retained payload bytes, and relevant active profile,
   resource, unit/effective-config/readiness and ownership facts must agree with
   the specifically approved transition. Equal bytes, a process exit code or a
   self-reported generation path alone are insufficient.
5. **Record terminal ownership**: retain original roots/journals/intent and mark
   transferred only after proof. Native dedicated mutation stays refused. Reverse
   transfer needs a different approved contract; never reset owner/registry files.

Current core recording happens **after** an external handoff is already proved.
It is not the staged orchestrator above and supplies no native generation-proof
adapter. The original intent/preparation stages and completion-after-crash rules
need explicit design; do not connect `record_transfer` directly to an arbitrary
successful HM command and call orchestration complete.

## 5. Proposed source-test matrix (not executed controller tests)

A future implementation must cover eligibility and refusal for each failure row,
not just a healthy example. Include at minimum:

- Report-only references/raw phase strings cannot authorize a resolution or select
  arbitrary paths, commands, helpers, backup producers or external actions.
- Missing/stale/forged/duplicate proof, legacy missing helper ownership, ambiguous
  effects, changed boot/time/source/unit/profile/root/resources or quota exhaustion
  block; no backfill of absent evidence.
- Equal bytes with new symlink identity, changed parent, hardlink, foreign/HM owner,
  partial pair, unavailable metadata and unclosed helpers remain quarantined.
- Every intent/record/fsync/CAS boundary is fault-injected. Original incident and
  consumed review remain immutable; partial completion never unlocks admission.
- New/old reader compatibility refuses unsupported resolution metadata. Retention
  counts include resolved incidents; no reset, purge or quota bypass.
- Handoff cannot overlap ordinary publication, root verification or another
  handoff; an external activation that leaves dedicated links unchanged is not
  ownership transfer. Failed external work remains blocked.
- Inspection/source fixtures never invoke real credentials, services, profiles,
  processes/groups, roots, app/library state or devices. Actual-stage approval
  remains separate even after successful source tests.

This document changes no runtime byte or state schema. The current regression
suite tests existing functionality, not these proposed controllers. Follow #128
for the decision and exact next scope; no new backlog is maintained here.
