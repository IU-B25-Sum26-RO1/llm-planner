# Team TODO - LLM Planner

This is the execution backlog derived from the proposal, the 2026-09-04 code
review, and the current repository state. The deployment and runtime acceptance
environment is **Windows 10/11 + WSL2 Ubuntu + Docker + ROS 2 Humble**. macOS may
be used for source-level checks only; it cannot close any Windows/WSL2 runtime
task below.

## How to use this backlog

- Create one GitHub issue per ID and use the issue type in the `Type` column.
- Replace role names with actual team members when assigning issues.
- Use branch names `<issue-number>-<short-name>` as required by
  `CONTRIBUTING.md`.
- Do not close an issue from screenshots or nominal logs. Attach the evidence
  listed in its `Done when` field.
- A task marked `Blocked` must not start until every listed dependency is done.

Sizes describe relative scope, not calendar estimates: `S` is a focused change,
`M` spans a component, `L` spans multiple ROS nodes, and `XL` is research plus
implementation and evaluation.

## Recommended ownership lanes

| Lane | Primary owner role | Scope |
|---|---|---|
| Platform | Windows/ROS engineer | WSL2, Docker, ROS graph, Gazebo, CI |
| Planning | LLM/backend engineer | schema, prompt, decomposer, evaluation |
| Perception | CV/robotics engineer | SAM3/RGB-D, poses, scene graph |
| Control | Motion-control engineer | MoveIt, skills, controller results |
| Learning | ML/robotics engineer | demonstrations, ACT/VLA policies |
| Safety/QA | Safety and test owner | verifier, recovery, hazards, release gates |
| Documentation | Documentation/demo owner | setup guide, evidence, video, presentation |

One person may own multiple lanes, but every issue must have a different reviewer.

## Phase 0 - integrate and prove the repaired baseline

These issues are the immediate sprint. No proposal feature should be claimed as
working until `WIN-01` through `EVAL-02` are complete.

| ID | Type | Owner | Size | Depends on | Task | Done when |
|---|---|---|---|---|---|---|
| `REL-00` | Task | Platform | M | - | Split the current reviewed worktree into reviewable PRs: command contract/safety, camera/audio/SAM3, dependencies, tests/evaluation, and docs. Preserve all regression tests and avoid mixing unrelated formatting. | Each PR is linked to an issue, reviewed, and merged; clean checkout passes `uv lock --check`, `pytest`, Ruff, Compose config, and shell syntax checks. |
| `WIN-01` | Task | Platform | M | `REL-00` | Build the image from a clean checkout on Windows/WSL2 using `docker compose build`. Record Windows build, WSL distribution, Docker, Compose, and GPU/WSLg versions. | Build exits 0 without manual container edits; complete build log and version manifest are attached to the issue. |
| `WIN-02` | Bug | Platform | M | `WIN-01` | Run `tests/docker-compose-control-smoke-test.sh` and repair any ROS interface generation, package, startup-order, or discovery defect it exposes. | Script exits 0 three consecutive times after clean container recreation and proves one `BaseAction` server plus the Task Manager client. |
| `SIM-01` | Task | Control | M | `WIN-02` | Add a headless Gazebo smoke test for `go_home`, `open_gripper`, `close_gripper`, `pick green_cube`, and `place white_tray`. | Automated test records action terminal state, timeout, final arm error, held-object state, and final Gazebo model pose; all five cases pass three seeded runs. |
| `ASR-01` | Task | Platform | S | `WIN-01` | Verify the new `text_replay` node and `evaluation/recognized_text_smoke.txt` on WSL2, then verify Vosk separately with a fixed WAV fixture. | Text replay publishes all four lines in order; a checked-in or downloadable licensed WAV produces the expected normalized transcript; logs are saved. |
| `ASR-02` | Task | Planning | M | `ASR-01`, `EVAL-01` | Resolve the proposal's explicit Whisper-ASR step: benchmark Whisper against the current Vosk implementation for Russian speech, then integrate Whisper or approve Vosk as a documented substitution. | ADR reports dataset/license, word error rate, command accuracy, latency, CPU/GPU/RAM use, offline behavior, and WSL2 reproducibility; selected ASR passes the same fixed audio corpus. |
| `LLM-01` | Task | Planning | S | `WIN-01` | Configure the selected OpenAI-compatible endpoint and run `scripts/evaluate_decomposer.py --trials 3`. | Versioned JSON artifact contains 42 trials across 14 cases, endpoint/model/config identifiers, zero schema-invalid responses, and documented failures. |
| `LLM-02` | Bug | Planning | M | `LLM-01` | Fix prompt/schema/model mismatches found by the live evaluation without weakening expected fields or silently remapping invalid output. | `LLM-01` exact pass rate is 100% for three consecutive evaluation runs; regression cases cover every repaired failure. |
| `EVAL-01` | Task | Safety/QA | M | `SIM-01`, `LLM-02`, `ASR-01` | Create an end-to-end manifest joining utterance, expected plan, scene seed, skill preconditions, verifier predicate, timeout, and artifact paths. | At least 10 commands have machine-readable expected outcomes and can be replayed without editing code. |
| `EVAL-02` | Task | Safety/QA | M | `EVAL-01` | Run and archive the repaired baseline before adding learned policies. | Report includes plan exact match, per-skill success, full-task success, stop latency, failures, seeds, ROS logs, and Gazebo state; results are reproducible from a clean WSL2 checkout. |

## Phase 1 - close semantic and perception gaps

These issues convert the current name-based scripted demo into a closed-loop
robotics system. Work may proceed in parallel after Phase 0, following the listed
dependencies.

| ID | Type | Owner | Size | Depends on | Task | Done when |
|---|---|---|---|---|---|---|
| `OBS-01` | Feature | Safety/QA | M | `EVAL-01` | Define ROS messages for `SceneObject`, `SceneObservation`, and `SkillResult`, including identity, class, attributes, 3-D pose/frame, confidence, timestamps, gripper/contact state, failure cause, and evidence references. | Interface package builds; messages have versioned examples and tests for missing/stale frames, low confidence, unknown objects, and explicit failure states. |
| `SKL-01` | Feature | Planning + Control | L | `OBS-01`, `SIM-01` | Implement a modular registry for 5-8 high-level skills. Each skill must declare typed arguments, preconditions, postconditions, timeout, cancellation behavior, safety policy, and typed result; the LLM may call only registered skills. | Registry exposes 5-8 tested skills through one versioned contract; unknown/unavailable skills are rejected; planner schema is generated from or checked against the registry; at least 3-5 skills later meet the measured working-skill gate. |
| `PER-01` | Feature | Perception | L | `OBS-01` | Convert camera/SAM3 output into calibrated 3-D object poses. Select and document the depth source, camera intrinsics/extrinsics, timestamp synchronization, and frame transforms. | Known-object pose error is measured on a calibration scene; stale/unsynchronized frames are rejected; output uses `SceneObservation`. |
| `PER-02` | Feature | Perception | L | `PER-01` | Add persistent object identity and a scene graph instead of deriving Gazebo names from English prompts. | Multiple same-class objects retain stable IDs through motion/occlusion tests; create/update/lost transitions are logged and tested. |
| `SEM-01` | Feature | Planning | M | `PER-02` | Implement `search_space` filtering and `selection` (`nearest`, `leftmost`, `largest`, and all other accepted enum values) against the scene graph. | Every accepted selection enum has positive, empty-result, tie, and stale-observation tests; the chosen physical object ID reaches the skill goal. |
| `SEM-02` | Feature | Control | L | `PER-02`, `OBS-01` | Implement geometry for `inside`, `on_top_of`, `left_of`, `right_of`, `near`, and the remaining accepted placement relations. Reject relations that cannot be satisfied safely. | Each accepted relation has a measurable world-state predicate, collision-free candidate generation, and seeded Gazebo success/failure tests. |
| `DET-01` | Task | Perception | M | `EVAL-02` | Decide whether SAM3 formally replaces the proposal's YOLOv8 detector or whether YOLOv8 is still required. Record an ADR comparing latency, class/open-vocabulary behavior, localization needs, data requirements, and measured accuracy. | ADR is approved and the proposal-compliance table names the chosen detector with benchmark evidence; no undocumented substitution remains. |

## Phase 2 - verifier and bounded replanning

| ID | Type | Owner | Size | Depends on | Task | Done when |
|---|---|---|---|---|---|---|
| `VER-01` | Feature | Safety/QA | L | `OBS-01`, `PER-01`, `SIM-01` | Implement postconditions for approach, contact, grasp, transport, placement, gripper open/closed, and home. Do not infer success solely from a commanded trajectory. | Every skill returns typed `SkillResult`; injected misses, dropped objects, stale vision, absent force, and wrong-object cases fail with explicit causes. |
| `VER-02` | Task | Safety/QA | M | `VER-01` | Calibrate confidence thresholds and timeout policy using repeated seeded trials. | False-success and false-failure rates plus confidence calibration are reported; thresholds are configuration, not prompt text. |
| `REP-01` | Feature | Planning | L | `VER-01`, `OBS-01` | Add a bounded recovery state machine: observe, classify failure, retry or safe retreat, replan, and terminal abort. | Retry budgets and allowed transitions are explicit; tests cover recoverable miss, unreachable target, object loss, timeout, repeated failure, cancellation, and stop during recovery. |
| `REP-02` | Task | Safety/QA | M | `REP-01`, `EVAL-01` | Measure recovery rather than demonstrating only successful runs. | Evaluation reports recovery-attempt rate, recovery success, terminal failure correctness, retry count, and time-to-safe-state. |

## Phase 3 - motion and physical safety

`SAFE-01` through `SAFE-04` are mandatory before connecting autonomous execution
to a physical UR10/ROZUM. Voice or LLM `stop` is not a hardware emergency stop.

| ID | Type | Owner | Size | Depends on | Task | Done when |
|---|---|---|---|---|---|---|
| `MOT-01` | Feature | Control | L | `SIM-01`, `PER-01` | Replace direct one-point trajectory publication with MoveIt/controller action execution and a maintained planning scene. | Self/environment collision checks, joint limits, velocity/acceleration limits, controller result, timeout, and cancellation are enforced and integration-tested. |
| `SAFE-01` | Feature | Safety/QA | L | `MOT-01` | Define an independent emergency-stop and protective-stop architecture below the LLM layer. | Hazard analysis identifies stop categories and reset rules; hardware/simulator tests prove stop latency and that software restart cannot bypass the stop state. |
| `SAFE-02` | Feature | Safety/QA | M | `PER-02`, `MOT-01` | Enforce allowlisted objects, permitted workspace zones, forbidden zones, and task-independent hard speed/force limits below the planner. | Disallowed object/zone and excessive speed/force requests are rejected even when sent directly to the action server. |
| `SAFE-03` | Feature | Perception | L | `PER-01`, `SAFE-02` | Add human-presence/exclusion-zone gating appropriate to the selected sensor setup. | Entering the exclusion zone triggers the defined protective response; sensor loss fails safe; false-stop/missed-stop tests are recorded. |
| `SAFE-04` | Task | Safety/QA | L | `SAFE-01`, `SAFE-02`, `SAFE-03`, `VER-02` | Perform formal risk assessment and staged commissioning: simulation, guarded dry run, supervised object trials, then approved operation. | Risk register, mitigations, residual-risk acceptance, commissioning checklist, and independent reviewer sign-off are stored with the release. |

## Phase 4 - learned grasp and place policies

The proposal requires at least two **trained** policies. Scripted IK plus Gazebo
attachment is a baseline and must not be reported as trained grasp/place.

| ID | Type | Owner | Size | Depends on | Task | Done when |
|---|---|---|---|---|---|---|
| `POL-00` | Task | Learning | L | `EVAL-02`, `OBS-01`, `VER-01` | Specify the grasp/place benchmark, observation/action spaces, demonstration format, train/validation/test split, randomization, baselines, success predicates, and compute budget. | Approved experiment plan prevents train/test leakage and can reproduce one baseline run from versioned config. |
| `POL-01` | Feature | Learning | XL | `POL-00`, `MOT-01` | Collect demonstrations and train the first policy for grasp (ACT or a justified alternative). | Training code/config, dataset manifest/license, checkpoint hash, learning curves, and held-out grasp success rate are versioned; inference uses bounded skill/action interfaces. |
| `POL-02` | Feature | Learning | XL | `POL-00`, `MOT-01` | Collect demonstrations and train the second policy for place (ACT or a justified alternative). | Same artifacts as `POL-01`, plus relation/target placement error and held-out placement success rate. |
| `POL-03` | Task | Learning | L | `POL-01`, `POL-02`, `VER-01` | Compare scripted baseline, trained policies, and—if feasible—a pretrained VLA supervisor interface using identical tasks and limits. | Report contains repeated-trial confidence intervals, failure categories, latency, and full-task success; policy choice is evidence-based. |
| `HIL-01` | Task | Learning | XL | `POL-03`, `SAFE-04` | Decide whether optional HIL-SERL is justified. Run it only if offline policies and safety gates are stable. | Approved go/no-go ADR; if go, human-feedback protocol, rollback, safety envelope, and comparative results are documented. |

## Phase 5 - CI, documentation, demo, and release

| ID | Type | Owner | Size | Depends on | Task | Done when |
|---|---|---|---|---|---|---|
| `CI-01` | Task | Platform | M | `WIN-02` | Add CI for Python 3.10 lock validation, unit/regression tests, Ruff, JSON manifests, shell syntax, and ROS package build. Use a Linux/ROS runner; use a WSL2 self-hosted runner for Windows-specific acceptance. | Required checks run on every PR; a deliberately broken schema/package/test is shown to fail the correct job. |
| `CI-02` | Task | Platform | L | `SIM-01`, `EVAL-01` | Add deterministic headless simulation jobs and artifact retention. | CI preserves scene seed, command manifest, logs, action feedback, observations, masks, final world state, and summary metrics. |
| `DOC-01` | Task | Documentation | M | `WIN-02`, `ASR-01`, `LLM-01` | Rewrite setup/troubleshooting from a clean Windows/WSL2 installation and remove commands not reproduced by the team. | A second team member follows the guide on a clean WSL2 environment without undocumented help and records the successful run. |
| `DOC-02` | Task | Documentation | S | `DET-01`, `POL-03`, `REP-02` | Maintain the architecture and proposal-compliance matrix with links to evidence, model/data licenses, limitations, and safety scope. | Every proposal row links to a merged implementation and measured artifact or is explicitly marked incomplete. |
| `DEMO-01` | Task | Documentation | M | `EVAL-02`, `REP-02`, `POL-03` | Script and record the proposal demo, including at least one recovery and one safe refusal—not only successful nominal runs. | Video shows configuration/version, voice input, plan, observations, execution, verification, recovery/refusal, and result metrics without hidden manual intervention. |
| `PRES-01` | Task | Documentation | M | `DEMO-01`, `DOC-02`, `SAFE-04` | Produce the final presentation from measured results. | Slides cover architecture, datasets, policies, evaluation design, confidence intervals, failure analysis, safety limits, proposal compliance, and future work; all figures cite artifacts. |
| `REL-01` | Task | Safety/QA | M | all required non-optional issues | Run the release audit against the gates below. | Reviewer signs a requirement-by-requirement checklist and the release is reproducible from a tagged clean checkout. |

## Dependency order and safe parallel work

```text
REL-00
  -> WIN-01 -> WIN-02 -> SIM-01 --------------------------+
             |          |                                 |
             |          +-> ASR-01                        |
             +-> LLM-01 -> LLM-02                         |
                            |                              |
SIM-01 + LLM-02 + ASR-01 -> EVAL-01 -> EVAL-02            |
                              |       +-> ASR-02           |
                              |                            |
             +----------------+------------------+         |
             v                                   v         v
           OBS-01 -> PER-01 -> PER-02        VER-01 <- SIM-01
              +----> SKL-01
                         |        |              |
                         |        +-> SEM-01     +-> REP-01 -> REP-02
                         |        +-> SEM-02
                         +-> MOT-01 -> SAFE-01/02/03 -> SAFE-04
                                      |
OBS-01 + VER-01 + EVAL-02 -> POL-00 -> POL-01 + POL-02 -> POL-03
                                                                |
              CI/documentation can follow completed evidence ---+
```

Parallel assignments after Phase 0:

- Perception owner: `OBS-01`, `PER-01`, `PER-02`, `DET-01`.
- Planning owner: `SEM-01`, then `REP-01` with Safety/QA.
- Control owner: `MOT-01`, then `SEM-02`.
- Learning owner: prepare `POL-00`; collection/training waits for stable interfaces.
- Platform owner: `CI-01` and reproducible WSL2 setup.
- Documentation owner: capture evidence continuously; do not wait until the demo.

## Release gates

### Simulation milestone

- [ ] Clean Windows/WSL2 build and ROS smoke test pass.
- [ ] At least 10 versioned commands run end to end with stored artifacts.
- [ ] All six planner actions have executable preconditions and postconditions.
- [ ] The modular registry exposes 5-8 bounded JSON-callable skills.
- [ ] Per-skill and full-task success rates are measured across repeated seeds.
- [ ] Stop/cancel, timeout, malformed input, missing object, queue-full, and
      unavailable-service failures are tested.
- [ ] No placement or selection field is silently discarded.

### Proposal-complete milestone

- [ ] Voice -> plan -> execution -> observation-based verification is proven.
- [ ] Two trained policies, grasp and place, have code, data manifests,
      checkpoints, and held-out metrics.
- [ ] Three to five skills meet predefined success thresholds.
- [ ] Bounded recovery/replanning is measured on injected failures.
- [ ] Detector choice and any departure from YOLOv8/ACT are justified by an ADR.
- [ ] Whisper is integrated or its replacement is justified by a measured ADR.
- [ ] Documentation, demo video, and final presentation are complete.

### Physical-robot milestone

- [ ] MoveIt/controller execution and planning-scene collision checks are active.
- [ ] Independent E-stop/protective stop is tested.
- [ ] Hard limits and allowlists are enforced below the LLM.
- [ ] Human exclusion and sensor-loss behavior fail safe.
- [ ] Formal risk assessment and independent commissioning approval are complete.

Until every applicable box is checked with linked evidence, describe the system
as a **simulation prototype**, not as “working as planned” or ready for physical
deployment.
