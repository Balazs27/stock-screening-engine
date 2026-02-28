# Active Plan

Use this template when planning multi-step refactoring, new feature implementation, or architectural changes.

---

## Plan Title
<!-- One-line description of the change -->

## Status
<!-- DRAFT | IN PROGRESS | COMPLETE | ABANDONED -->
DRAFT

## Objective
<!-- What is the end goal? Why is this change needed? -->

## Impacted Models
<!-- List every dbt model, Python file, or DAG that will be modified -->

| File | Change Type | Description |
|------|------------|-------------|
| | | |

## Contract Changes
<!-- Document any grain, column, or type changes -->

| Model | Change | Before | After |
|-------|--------|--------|-------|
| | | | |

## Backfill Strategy
<!-- How will existing data be handled? -->

- [ ] Full refresh required (dbt run --full-refresh)
- [ ] Incremental catch-up (no action — next daily run picks up)
- [ ] Manual backfill needed (specific date range)
- [ ] No backfill required (additive change only)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| | | | |

## Downstream Impacts
<!-- What consumers (MCP, Superset, other models) are affected? -->

- [ ] MCP semantic layer needs updating
- [ ] Superset dashboards need updating
- [ ] Downstream dbt models need updating
- [ ] No downstream impacts

## Validation Plan

### Pre-Change Baseline
<!-- Capture current state metrics before making changes -->
```sql
-- Row counts, score distributions, etc.
```

### Post-Change Verification
<!-- Tests and queries to run after implementing changes -->
- [ ] `dbt test --select {affected_models}`
- [ ] Row count comparison (pre vs post)
- [ ] Score distribution comparison
- [ ] Spot-check specific tickers
- [ ] Verify MCP queries still return expected results

## Rollout Plan

| Step | Environment | Action | Checkpoint |
|------|------------|--------|-----------|
| 1 | dev | Implement changes | dbt build succeeds |
| 2 | dev | Run validation queries | Results match expectations |
| 3 | dev | Run full test suite | All tests pass |
| 4 | prod | Deploy (change target in profiles.yml) | dbt build succeeds in prod |
| 5 | prod | Verify MCP + Superset | Consumers return expected data |

## Rollback Plan
<!-- How to revert if something goes wrong -->

---

*Delete this template content when populating with an actual plan.*
