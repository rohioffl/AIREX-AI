# Runbook: Manual Review & Rejection Workflow

When automation cannot safely proceed, incidents should be moved into **manual review** instead of attempting risky fixes. This runbook explains how to capture operator context, where those notes surface, and how to resume automation later.

## When to reject an incident

- Investigation output is inconclusive or points to a human-only remediation.
- Recommended action is unsafe for the current environment (e.g., maintenance window, partial outage).
- You already handled the alert outside of AIREX and want to archive it with a note.

## Adding the operator note

1. Open the incident in the dashboard.
2. Under **Approval Required**, use the **Reject (Skip)** form.
3. Enter a short explanation (min 3 characters, max 500). This text becomes the canonical `_manual_review_reason` stored in `incident.meta` and the transition log.
4. Confirm the rejection. The incident transitions to `REJECTED`, and the note + timestamp are preserved.

## Where the note appears

- **Alerts page**: incidents flagged for manual review show a red “Manual Review” pill and the note. This includes cases where automation flagged `_manual_review_required` (e.g., investigation retries exhausted).
- **Rejected page**: every row shows the latest operator note and timestamp so reviewers can triage quickly.
- **Incident detail**: the header highlights the most recent transition plus a dedicated “Operator note” card with the text and time. Timeline history also records the transition reason.

## How to resume automation (optional)

1. Investigate manually (SSH, logs, etc.).
2. If additional automation is desired, create a new incident (e.g., by re-triggering the monitor) or manually change the state via SQL/AIREX tooling after clearing the `_manual_review_required` meta flag.
3. Document any follow-up actions in the incident comment system (coming soon) or the runbook of record.

## Metrics & reporting

- Prometheus metric `manual_review_total` increments whenever `_manual_review_required` is set.
- Use `/api/v1/incidents/?state=REJECTED` or filter by `meta._manual_review_required` to build custom reports.

## Notes

- Backend services **must never** transition directly to `REJECTED`. They should leave incidents in `FAILED_*` states with `_manual_review_required=true` so operators can make the final decision.
- If you accidentally rejected an incident, reopen it by cloning the alert (Site24x7 “Send test alert”) and letting automation re-run.
