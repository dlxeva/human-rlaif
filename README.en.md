Write down your judgment, let AI challenge one key point, then check it against what actually happens.

- Before: decide by feel → With this: record your judgment, reasons, and probability
- Before: ask AI for the answer → With this: save your own first draft
- Before: move on after a chat → With this: examine one counterexample or trade-off
- Before: judge only the finished work → With this: compare the forecast with the outcome
- Before: assume “I get it” → With this: pick a date and try a new task

These are workflow changes, not measured learning gains.

# human-rlaif

[中文](README.md) · [Install and start](#install-and-start) · [Skill entry point](skill/human-rlaif/SKILL.md) · [Research paper](paper/README.md)

An Agent Skill for practicing judgment through AI feedback and real-world checks.

**Evidence boundary:** A v0.1-series reference implementation, grounded in a single-author exploratory self-case study, with no guarantee of effectiveness. “Reinforcement Learning” is a metaphor for human practice and feedback; this project does not train a model or update model parameters.

**Evaluation summary:** Tests covered initial Agent responses to synthetic tasks, read-only recovery, and the file helper. Of the original 16 cases, 11 response checks passed, 1 failed, and 4 lacked required conditions; a separate cloud run passed 3 response checks and 1 read-only recovery check, with details in the [run records](evals/runs/). Full installation and continuous recovery in a strongly isolated host, plus a real person's action followed by a new-task retest at least 7 days later, remain outstanding; see the [current acceptance report and human-run template](evals/runs/2026-10-17-requirements-v2/), which synthetic examples cannot replace.

## When to use it

Use it for a real decision you want to practice: choosing a plan, assessing evidence, reviewing a mistake, or checking whether you have learned something. Say “review my judgment”, “help me practice judgment”, or “start human-rlaif”; say “just help me deliver today” to switch to `production`. The three modes are delivery (`production`), practice (`learning`), and evaluation (`assessment`).

## Install and start

Give your Agent this request:

> Install the skill/human-rlaif/ skill directory from https://github.com/dlxeva/human-rlaif. First read its SKILL.md and references/install.md, confirm the host and absolute destination, and preserve existing skills. Start with my real problem in three steps: save my judgment and outcome probability, give one key challenge, and agree on a new-task retest date. After 2–3 short loops, draft the full HUMAN.md agreement and baseline for me to confirm. Ask separately before saving private records, and do not upload them.

Install only `skill/human-rlaif/`, without the paper, tests, or whole repository. There is no long form to complete on day one. Honest information, visible unknowns, a first draft before feedback, and human responsibility for real-world actions apply from the start. See the [minimal dialogue](skill/human-rlaif/references/examples.md) and [bilingual glossary](skill/human-rlaif/references/glossary.md).

## Save, check due items, and calibrate

Keep the private workspace outside Git working trees and synced folders such as iCloud or Dropbox. The optional helper requires Python 3.10+; from the repository root:

```bash
python skill/human-rlaif/scripts/workspace.py init --workspace /absolute/private/path
python skill/human-rlaif/scripts/workspace.py record --workspace /absolute/private/path --event /absolute/path/event.json
python skill/human-rlaif/scripts/workspace.py due --workspace /absolute/private/path
python skill/human-rlaif/scripts/workspace.py calibration --workspace /absolute/private/path
```

The Agent is instructed to check due items at the start of each session; the script does not start itself or send notifications. Calibration compares advance probabilities with later outcomes and reports sample counts, hit rate, and Brier score. See [installation](skill/human-rlaif/references/install.md) and [protocol](skill/human-rlaif/references/protocol.md) for usage, v1/v2 compatibility, and local data-minimized exports.

## Development, citation, and license

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
skills-ref validate skill/human-rlaif
python scripts/validate_human_rlaif.py
python -m unittest discover -s tests -p 'test*.py' -v
```

[Behavior evaluation protocol](evals/HUMAN-RLAIF.md) · [Research and citation](paper/README.md) · [Related project: pbl-loop](RELATED_PROJECTS.md) · [Software citation](CITATION.cff)

Public code and original documentation use [MIT](LICENSE). The paper follows the copyright and license of its published version. Users control their private records.
