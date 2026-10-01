# M2 Team Contributions (Draft Template)

This is a working template for the 2026-10-04 interim submission. The role descriptions below come from `docs/plan/04-workstreams.md`; repository examples are limited to facts visible in the checked-in plan, handoffs and Git history. A commit author or role tag is evidence of a recorded change, not proof of a person's full contribution or identity. Team members should fill in names, review the evidence and confirm the final wording.

| Planned role | Member name (team to confirm) | Planned M2 responsibility | Verifiable repository evidence to review | Member confirmation | Team review |
|---|---|---|---|---|---|
| A | `[待确认]` | Frontend and visualization; demo packaging, 3-minute video and interim submission (plan: `04-workstreams.md`, `05-timeline.md`) | Frontend implementation and integration notes exist in `frontend/M1-IMPLEMENTATION.md` and `frontend/M1-INTEGRATION.md`. Git history includes the M1 event-to-reroute integration commit `41b9347`; confirm which work belongs to this member before attributing it. The M2 video itself is not yet evidenced as recorded. | `[待本人确认]` | `[待团队确认]` |
| B | `[待确认]` | Event pipeline and review workflow; source/provenance and AI-boundary content (plan: `04-workstreams.md`) | `docs/coordination/B-M2-progress-evidence.md` and `B-M2-event-pipeline-report.md` document B-side implementation and validation boundaries. Git history includes B-labeled handoff/check commits such as `f1f7a1a`, `1de6fa9`, `4109ee7` and `5b1082f`; confirm the member mapping and final accepted scope. | `[待本人确认]` | `[待团队确认]` |
| C | `[待确认]` | Route/network/simulation work, data provenance and deployment (plan: `04-workstreams.md`; M2 deployment in `05-timeline.md`) | The branch contains the explicitly labeled `[M1][C-Sim]` commit `8bf29fe` and C-side acceptance/handoff materials. These are evidence of prior C-side work, not by themselves proof that M2 deployment or a 10,000-person simulation passed. Confirm any M2-specific deliverables and their validation. | `[待本人确认]` | `[待团队确认]` |
| Shared / other | `[待确认]` | Cross-role integration, review, testing, or other agreed contribution | `[Add exact file, handoff, issue, or commit and describe the contribution it demonstrates.]` | `[待本人确认]` | `[待团队确认]` |

## Before submission

- Replace role labels with names only after the team confirms the mapping.
- Cite specific files, issue IDs, test records or commit IDs for each claimed contribution; distinguish implementation, review and validation.
- Remove claims that lack evidence or are not confirmed by the named contributor.
- Do not present planned responsibilities as completed work. Record M2 deployment, video production, and other deliverables as pending until their artifacts or verification records exist.

## Interim package checklist

- [x] Team contribution table template drafted here; names and contribution claims still require member/team confirmation.
- [ ] Architecture diagram PNG: pending output from C, per `docs/plan/05-timeline.md`.
- [ ] Public deployment: not verified; add a URL only after an external availability check.
- [ ] 3-minute MP4 with Chinese and English subtitles: not produced.
- [ ] GitHub Project board snapshot: pending confirmation of the actual board and capture; no board creation or screenshot is claimed here.
- [ ] Interim package submission: planned for 2026-10-04; check the artifacts before marking submission complete.

## Next milestones

- **P3, 2026-10-05 to 2026-10-11:** work toward the three demo acceptance targets. The plan schedules the initial 10,000-person simulation run for 2026-10-07, comparisons for 2026-10-08 to 2026-10-09, and the M3 checkpoint on 2026-10-11; these dates are plans, not completion evidence.
- **P4, 2026-10-12 to 2026-10-18:** data calibration and bug bash; feature freeze on 2026-10-14; final deployment, performance checks, offline fallback, final video and presentation, rehearsals, and final delivery on 2026-10-18.
