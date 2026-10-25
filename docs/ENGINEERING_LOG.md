# Engineering log (observed issues and planned mitigations)

Recording format: timestamp · environment · symptom/reproduction · root cause · fix · verification command + output · remaining uncertainty.

## 2026-10-26: design and GitHub initialization
- **Q-001 Possible look-ahead:** using close(t)-to-close(t+1) returns as though a close(t) order could be filled. Preventive fix: explicit features through close(t), target next-open(t+1) to following-open(t+2). Automated feature/label tests. Status initially pending execution.
- **Q-002 Model selection leakage:** tuning on future test data or training labels unavailable at a fold boundary. Preventive fix: two-session date separation for labeled observations at validation and test starts; select candidate only on preceding validation data. Boundary assertions and tests. Status initially pending execution.
- **Q-003 Transaction-cost understatement:** switching a position sells old + buys new; net vs gross benchmark unfair. Fix: charge absolute weight change to both model and equal-weight benchmark; test a two-session switch.
- **Q-004 Invalid market claim:** toy data can produce convincing but meaningless Sharpe. Fix: mark synthetic source explicitly in README, CLI manifest and output.
- **Q-005 Dynamic universe / halted asset problem:** cannot safely forward-fill an open price for an untradeable asset. Fix in v0: reject unbalanced panels. Remains **open**: survivorship bias, changing membership, corporate actions, liquidity.
- **Q-006 Platform dependency:** Mac system Python was reported as 3.9.6 (too old for project) and base system lacked numpy/pandas/sklearn/lightgbm/pytest. Fix: use existing Python 3.12 located at ~/.local/bin/python3.12 in a project .venv. Verification pending actual install and test result.
- **Q-007 GitHub action source preparation:** a multi-file upload script was rejected by the JS parser before any new files from that batch were created. Fix: split into smaller, syntactically isolated GitHub file commits. Verification: targeted GitHub create_file commits for tests, followed by repo inspection.

## Mac validation
**Not yet recorded as successful.** Add exact command output, failing assertions, root causes, commits and rerun status after executing tests.

## Real-market experiments
**Not run.** Qlib integration is optional/untested with real datasets; any true financial performance statement must include source, timestamps, point-in-time/universe analysis, fee assumptions and out-of-sample results.
