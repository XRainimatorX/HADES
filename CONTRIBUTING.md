# HADES Development Discipline

`CONTRIBUTING.md` — Reference document.

This is a reminder of working discipline, based on the general software development process. It is a reference only: it does not set technical requirements, values, or functions.

**The same cycle is followed once in every stage of the project.** Each stage begins at Step 0 and is not finished until Step 7 is complete.

```text
Design → Contract → Test Plan → Skeleton → Parallel Development
→ Integration Test → Code Quality → Documentation → Knowledge Transfer
→ Stage Complete
```

---

## Step 0 — Design and Planning

```text
□ Write the design before writing code.
□ Define the contracts and interfaces.
□ Plan how the work will be tested.
□ Map which parts depend on which.
```

Output: design notes, interface specification, test strategy.

---

## Step 1 — Foundation Setup

```text
□ Prepare the repository and branches.
□ Create the skeleton: directory structure and empty files.
□ Write a minimal test first; it is expected to fail at the start.
□ Set up CI/CD so tests run automatically.
```

Output: repository structure, working CI/CD, test fixtures.

---

## Step 2 — Parallel Development

```text
□ Split the work according to the contracts.
□ Each person or team builds their part in parallel.
□ Run unit tests on your own work.
□ Nobody blocks anybody, as long as the contracts and interfaces do not change.
```

Output: feature branches, unit tests.

---

## Step 3 — Integration Testing

```text
□ Each feature branch: pull request → code review → merge to main.
□ Run the integration test with every part working together.
□ All tests pass = the work is complete.
```

Output: merged pull requests, passing integration tests, test reports.

---

## Step 4 — Code Quality Check

```text
□ Test coverage ≥ 90%.
□ Linting passes (pylint / black).
□ Type checking passes (mypy).
□ Security scan passes (bandit).
```

Output: coverage report, linting report, security audit.

---

## Step 5 — Documentation

```text
□ Every public function has a docstring.
□ User documentation: README and Getting Started.
□ Architecture documentation: how it works and the design decisions.
□ FAQ and troubleshooting.
□ Benchmark results are recorded.
```

Output: complete docstrings, user guide, architecture document.

---

## Step 6 — Knowledge Transfer

```text
□ Handoff document: known limitations and future work.
□ Postmortem: what went well, what went wrong, what to improve next time.
□ Meeting notes are written up.
```

Output: handoff document, postmortem report.

---

## Step 7 — Stage Complete

```text
□ Confirm every work item in the stage has met its done criteria.
□ Stage summary: what was completed, what was fixed, what changed
  that affects others.
□ Update the changelog.
□ Tag the end of the stage in the repository, e.g. stage-2.
□ Announce the stage as complete to the team.
```

Output: stage summary, updated changelog, stage tag.

---

## Ongoing — Maintenance

Not part of a single stage; continues alongside all stages and after the project.

```text
□ Weekly: check for new bugs.
□ Monthly: check that test coverage has not dropped.
□ Quarterly: check that performance has not degraded.
□ Whenever a design mistake is found: correct the documentation.
```
