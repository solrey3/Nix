# Case #135: post-publication completion design (not operational)

[Jukebox #135](https://github.com/solrey3/Jukebox/issues/135), under
[deployment #131](https://github.com/solrey3/Jukebox/issues/131). Read with the
[general proposed recovery contract](jukebox-recovery-transfer-contract.md) and
[current publisher contract](jukebox-playback.md).

**Authorized delivery: source design and isolated synthetic fixtures ONLY.** No
writer, new CLI mode, accepted registry schema, live proof producer, admission
exception, ownership adoption, merge or production action is implemented here.
The existing reader must continue to refuse this incident. Generic recovery
#129/HM handoff #130 remain deferred; the settled bounded-baseline decision #128 A
is not being reopened. A new case-specific policy would need separate acceptance.

## 1. Case identity and what is not known now

The last recorded 31 October 2026 incident is review/transaction
`6d8401abad7355664ecba6d8a5ab2d1c`, artifact source
`c72abada5440cdb56e1776546dcb1ecade0933b8`, manifest SHA-256
`621a06c8cb376e2081d33f63826c3c39ac744f4fa3048f163474a8ebaab2e763`,
publisher identity `19c77f15347e03279c5b545ef1fa9f986bc20c22d3ae1f623b0c9d7a462e3023`.
It published canonical bravo/Music configuration and restarted the manager once;
final verification rejected a legitimate zero-loader-worker shape. Subsequent
source correction and independent read-only observations are documented in #131.

The native review remains consumed, transaction blocked, registry pending with
no current artifact/last terminal transaction. **Current=null does not mean public
absence.** Independent evidence was retained as reports 20/21 in the private
attempt evidence directory referenced on #131. Sealed backup ID
`3a8ed31f74a5627c47edd84a810bff0f` is historical evidence, not a future restoration
instruction. No private record contents, paths chosen by a record, token or
operational payload is included in the fixtures.

This design does NOT re-read those files, inspect the live system or establish
that dated observations still hold. The old publication code writes transaction
`ownership` only AFTER readiness succeeds; the false rejection therefore does
not leave a normal native terminal ownership record. An external snapshot must
not be silently treated as that missing record. Source analysis can define a
candidate proof contract, but **real-case admissibility remains unassessed**.

## 2. Three different results

| Result | Meaning | Admission |
| --- | --- | --- |
| Structural inspection | Describes retained metadata and coverage | Still blocked |
| External acceptance attestation | Records who accepted which separately verified historical/current facts | Still blocked; never native terminal success |
| Supported successor ownership/admission head | Would explicitly recognize one exact external acceptance under a new reviewed protocol | Not implemented or authorized |

A sidecar, corrected source, matching hash, user-visible successful app, receipt
or phase string alone is never the third result. No path may turn an old consumed
review back to pending, change its blocked phase to verified/discarded, or reuse
its expired plan. Do not call the resulting state a successful native transaction.

## 3. Candidate evidence contract (illustrative, not a file schema)

All evidence selection must be independently pinned outside the supplied record.
Digests identify bytes; they do not authenticate their producer, history or
approval. Unknown/missing/duplicate fields/domains or unsupported records refuse.
Bounds, owner/mode/link/ancestor checks and current-vs-historical time must be
explicit; do not select arbitrary paths, commands, APIs or producers from JSON.

| Domain | Required meaning / producer responsibility |
| --- | --- |
| Exact incident | Fixed account/host/state root, original registry/review/transaction byte digests and identities, consumed/blocked/pending relationships, applied artifact/source/code/backup/plan binding. No unrelated nonterminal work. |
| Historical verification | Independently selected retained report/provenance, exact producer source identity, approved action scope, observed publication/result and actual helper closure. A new report cannot fabricate the past or replace a missing exit receipt. |
| Ownership spine | Raw public links, active pointer, parents and their dev/inode/uid/mode/link-count/ctime/mtime identities match the independently selected historical snapshot; immutable payload/manifest and selected reference closure/registered root independently valid. Equal bytes with new identity still refuse. |
| Current runtime | Bounded known process/thread/child/cgroup membership and service/stop policy, current app capability/config/flags and profiles/source/tools; expected manager invocation selected independently. An unexplained restart/profile change is not auto-adopted. |
| Whole namespace | Exact bounded original state and retained-root/review/transaction inventory, no partial/unknown work, descriptor/identity checks before and after; ordinary mutation remains excluded. |
| Current resources | Fresh approved source/data/config/playlist-metadata observations and coherent private backup/proof appropriate to current state, not a convenient historical backup. No media walk, edit or restoration. |
| Fresh authorization | Distinct completion-only intent/review, current implementation/contract/incident/proof digests, same-boot UTC/monotonic bounded window, explicit effect scope. It is not an apply/rollback review or self-approval. |

The existing Jukebox deployment authentication channel can supply a safe private
FD within a future approved observation scope; do not reintroduce an unnecessary
operator token-copy step or mine browser/other-service credentials. This document
and its fixtures do not obtain any credential or contact an API.

### Historical and current data are separate domains

The original report may establish that publication preserved data THEN. User
library edits or legitimate app activity may have happened SINCE. Current data
must be compared with a freshly reviewed current dataset/backup, and differences
from historical observations explicitly acknowledged. Never restore a historical
DB, playlist, audio file or config just to make a stale plan's hash match. Neither
same historical hashes nor an unexplained new hash proves a safe completion.

The ownership spine is different: if raw link/parent identities changed, this
contract does not authorize foreign-path adoption or re-anchoring. Stop and retain
blocking state; do not recreate a matching link as supposed proof. Effective
flags/identity changes also need explicit analysis, not implicit permission to
enable broad writes or scheduling. Idle observations remain a coordinated-window
assumption, not atomic exclusion of all external editors/clients.

## 4. Proposed records and compatibility boundary

Names below are conceptual types, **not accepted serialization or commands**:

- **IncidentOriginals**: unchanged consumed review and blocked transaction, plus
  an immutable byte-for-byte before-image of the mutable registry head, exact
  digests/identities and historical evidence selection/provenance. Preserve old
  roots/backups and consumed IDs. A future CAS necessarily changes the live head;
  do not claim that it leaves that head's bytes unchanged. Preserve its original
  bytes separately BEFORE any CAS. Never rewrite review/transaction history.
- **ExternalAcceptance**: append-only, distinct ID, exact original/proof/producer/
  approval pins, explicit `external` origin and enumerated not-proved limitations.
  It can record accepted facts without granting native admission. It may not
  smuggle paths, shell callbacks, a backup producer or an artifact selector.
- **SuccessorHead**: a future explicitly versioned envelope with a typed EXTERNAL
  ownership anchor and a reference to exact immutable acceptance/originals/proof.
  Do not point a v1 terminal transaction field at an old blocked transaction as
  though it were verified. Do not merely clear v1 pending or invent `eligible`.

A future new reader would need strict version/field validation, fixed case/policy
selection, evidence closure and stable ownership semantics for BOTH ordinary
review and rollback. V1 normal operation must stay unchanged. Old readers must
refuse the new version/namespace, never silently ignore acceptance metadata. A
new reader must refuse incomplete/unsupported/ambiguous/doubled successors and
any unrelated nonterminal evidence. No migration/adoption at startup.

Placing an unsupported completion file inside today's namespace is itself
unknown evidence and blocks. Placing an external report outside it changes
nothing about today's admission. Both are exercised with the current reader.

## 5. Candidate protocol and crash requirements — no writer delivered

A future protocol would require a fresh explicit completion-only review after
independent evidence validation, not a repaired/replayed old apply:

1. Open existing trusted owner/lock non-queuing; no absent-state initialization.
   Verify exact original namespace and case pins, current proof, quotas and fixed
   scope. Any unknown or unavailable fact refuses before writing.
2. Retain synced originals/before-image and append completion intent. Retain
   existing records/roots/backups; do not hide them by moving/resetting live state.
3. Append bounded external proof/acceptance records and sync files/directories.
   At this point there is still NO native release. Current readers must refuse
   unsupported version/namespace, not become a permissive fallback.
4. Revalidate namespace, original hashes, raw ownership, boot/time/window and all
   case-specific facts immediately before an exact compare-and-swap of the
   expected head to a supported typed successor. No generic pending exemption.
5. Independently re-read the complete head/proof/namespace and complete the
   explicitly defined commit/acknowledgement protocol. A missing/uncertain sync,
   changed observation, incomplete receipt or lost result is NOT automatic success.
   Preserve uncertainty and require a new explicit review; no startup retry/resume.
6. Even a future accepted successor does not execute the old action. Any later
   ordinary update/rollback needs its own current review/approval/backup/window.

A CAS or final rename is NOT a multi-file atomic transaction. Filesystem durability
and a crash after commit but before acknowledgement need a concrete implementable
protocol, not an in-memory `fsynced=true` claim. A success-looking head by itself
must not conceal an unfinished commit. The acceptance/linearization point,
reader refusal rules, restart behavior and lost-ack case need explicit review and
real isolated syscall/fsync fault injection BEFORE a writer could be accepted.
This design does not claim those problems solved by a boolean model.

Candidate checkpoints enumerated by fixtures include existing lock, original pin,
historical/current proof, intent write/fsync, proof write/fsync, namespace recheck,
registry CAS/file/directory sync, independent re-read, commit receipt write/sync
and operator acceptance. Every model fault remains blocked with unchanged inputs.
**These labels do not simulate syscalls or prove real crash durability.**

## 6. What the delivered fixtures actually establish

- `tests/completion_contract_fixtures.py` is a PURE SYNTHETIC CLAIM-RELATIONSHIP
  model: no filesystem/network/credentials/processes/runtime imports. It is not
  a serializer, authenticated proof producer, clock, CLI or release validator.
  Even copied/forged consistent claims always return writes/actionable/native
  admission release FALSE and list authenticity/provenance/facts/durability/
  approval/feasibility as not verified. No positive operational release path.
- It checks fixed synthetic incident/original/artifact/history/producer binding,
  known distinct proof domains, ownership identity equality, fresh-window shape,
  historical-vs-current resource/backup/review relationships and later-edit
  acknowledgement. All IDs/records are invented, not loaded from #131 evidence.
- `tests/test_jukebox_completion_contract.py` also exercises REAL CURRENT CODE on
  synthetic home/store/database/API/commands: a post-publication verification
  refusal leaves consumed/blocked/pending state and published links. Corrected
  read-only observations pass, but apply/rollback/review/discard still refuse.
  External reports/design checkpoint labels cannot release it; unsupported ledger
  namespace refuses. Originals and fake service action count remain unchanged.
- No future registry-v2 writer/readers or syscall crash protocol is tested. A
  green design suite must not be presented as recovery implementation or evidence
  that the real retained incident now qualifies.

## 7. Feasibility and next gates

**Possible design direction:** preserve history and recognize external acceptance
as a DIFFERENT typed successor, never counterfeit native success. **Not yet
established:** historical snapshot/provenance sufficiency for this real case,
fresh current identity continuity, proof producer availability, or a safe complete
storage/acknowledgement protocol. Existing records do not provide all facts by
mere existence. Missing historical provenance cannot be manufactured now.

After source review, a separately specified/approved bounded READ-ONLY evidence
assessment could determine whether independently selected retained reports and
current facts meet this contract; report each gap/refusal without mutation. If
required proof cannot be established, keep the incident blocked. No actual
write-capable implementation, supported admission exception or live completion
follows from approval of these docs/tests. Those need their exact contract,
effects, source tests/fault coverage and explicit approval separately.

Until then, #131 remains blocked for publisher mutation and the last independently
verified configuration may serve for user testing. Do not infer playback-control
permission from that: the shared write flag and generic recovery/transfer scopes
remain unchanged/deferred. Follow #135/#131 for decisions; no parallel backlog or
operational repair recipe is maintained here.
