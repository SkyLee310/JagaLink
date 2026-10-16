# PRD: Community Early-Warning Safety Network

> Markdown transcription of `docs/PRD_Community_Early_Warning_Network_EN.pdf` (Draft v1, 16 Oct 2026).
> This file is the working copy agents read; the PDF is the frozen original.

Sime Darby Property University Hackathon 2026 | Track: PEOPLE, Safety & Security | Draft v1, 16 Oct 2026 | Author: Sky Lee

## 1. Background and Goals

This PRD defines the prototype for the Sime Darby Property University Hackathon 2026. It connects isolated CCTV cameras and sensors in a residential community into one spatial network, warns guards while unusual movement is still happening, and helps police rebuild a path afterwards. Proposal materials are due **23 Oct 2026, 23:59**.

**Hackathon context.** Theme: Township of Tomorrow. Judges score six criteria: Relevant, Impactful, Innovative, Feasible, Scalable, Evidence Based. The 23 Oct submission needs three things: a pitch deck of at most 10 pages, a 5-minute video or demo link, and a prototype or code link.

**Problem.** In guarded residential communities, cameras work as separate units, a few outsourced guards cannot watch every screen all night, and a break-in is usually noticed after it happens. Police then review footage camera by camera. Malaysia recorded 11,334 house break-in and theft cases in 2024, and 77.6% happened at night (DOSM, Crime Statistics Malaysia 2025). Full evidence and sources are in the separate Problem Statement.

### Product goals

- Shorten the time from the first unusual event to the right guard receiving an alert, compared with a baseline where guards check screens in turn.
- Turn after-the-fact path reconstruction across cameras from manual camera-by-camera review into one query.
- Reach both goals without facial recognition.
- Ship a prototype judges can understand in a 5-minute recorded demo.

### Success metrics (target values are suggestions for the team to confirm)

| Metric | How it is measured | Suggested target |
|---|---|---|
| Time from first unusual event to alert reaching the right guard | Timestamps in simulated scenarios, compared with a guards-check-screens-in-turn baseline | Below baseline; exact value set once the baseline is measured |
| Next-camera suggestion accuracy | Each scenario checked against the scripted true path | At least 80% |
| False alerts on normal traffic | Alerts per camera per night | At most 2 |
| Incident timeline match | Events, order and times compared with the script | At least 90% of events match |

**Scope and constraints.** Must features go into the 23 Oct submission. Should features are built after a Top 10 result, for the final submission on 11 Nov. The demo is a recorded video, not a live demo. The table below marks each gate.

### Key dates, 2026

| Gate | Date |
|---|---|
| Registration closes | 21 Oct |
| **Proposal submission** | **23 Oct** |
| Top 10 announced | 28 Oct |
| Mentoring | 2 Nov to 6 Nov |
| Final submission | 11 Nov |
| Pitch | 14 Nov |
| Top 5 notified | 17 Nov |
| Awards | 3 Dec |

## 2. User Personas

There are four user types. The security company operates the system and has access to the cameras; the property management company buys it. Guards use it every shift. Residents and police benefit from it. The table is based on public cases and team observation; no interviews have been done yet.

| Role | Situation | Goal | Pain point | Role in the system |
|---|---|---|---|---|
| Security company supervisor (operator) | Runs the outsourced guard team for a community and holds access to its cameras | Fewer incidents; faster, more consistent response from a small team | Guards cannot watch every screen; faults go unnoticed (a public case reported gate CCTV and central monitoring not working) | Sets up the camera layout, reviews alert records, assigns guards |
| Property manager (buyer) | Property management company that hires the security company and pays for the system | A safe community, accountability to owners, little new hardware | Little visibility of how well security actually works | Approves purchase; reads summary reports |
| On-duty / patrol guard (daily user) | Posted at a guard house or gate, or patrolling the community | Know quickly where something is wrong and where to go | Sees only the screen in front of them | Receives alerts, checks the suggested camera, confirms or dismisses |
| Resident (beneficiary) | Owner or tenant who pays for security | Peace of mind, and footage not misused | Break-ins happen even with guards; worry about CCTV misuse | No direct use in the prototype; privacy limits protect them |
| Police investigator (secondary) | Reviews footage after an incident | Rebuild a cross-camera path quickly | Review is slow (length unverified, no public data) | Uses post-incident path query (Should) |

Section 7 lists what interviews should validate. First priority: one security company supervisor.

## 3. User Stories

Twelve stories cover the user types and the judge's viewpoint. Each maps to a feature ID in section 4.

| ID | User story | Feature |
|---|---|---|
| US-1 | As a security supervisor, I want to place cameras on a community map and mark the links and walking times between them, so the system knows how cameras relate to each other. | F1 |
| US-2 | As a security supervisor, I want to evaluate the system with typical replayed scenarios, so I can judge its value without connecting real cameras. | F2, F8 |
| US-3 | As an on-duty guard, I want an alert the moment something unusual happens, so I do not have to watch screens constantly. | F4, F5, F6 |
| US-4 | As an on-duty guard, I want to know which camera to check first and which way the event is moving, so I can decide where to go. | F3, F5, F6 |
| US-5 | As an on-duty guard, I want to see why an alert was raised and confirm or dismiss it with one click, so I stay in charge of the response. | F6, F7 |
| US-6 | As a security supervisor, I want alerts ranked by severity, so guards are not buried in low-value alerts. | F4, F7 |
| US-7 | As a security supervisor, I want an automatic incident timeline after an event, so I can explain it to owners and police. | F7 |
| US-8 | As a resident, I want the system not to identify individuals or keep identifiable footage for long, so my privacy is protected. | F3, F12 |
| US-9 | As a police investigator, I want to enter a time window and see one anonymous cross-camera path, instead of reviewing each camera. | F11 |
| US-10 | As a security supervisor, I want the system to keep working when a camera goes offline and to show me the blind spot. | F9 |
| US-11 | As a judge, I want to see the system handle real public video, not only simulated data, so I can judge feasibility. | F10 |
| US-12 | As a security supervisor, I want the system to learn what normal movement looks like in my community, so rules fit the place and false alerts drop. | F13 |

## 4. Feature List

The 23 Oct prototype has 8 Must features. 5 Should features are for the 11 Nov final submission. 8 items are explicitly out of scope. A 3D layout view was moved to Won't: Sky confirmed 2D is enough.

### Must (needed for 23 Oct)

| ID | Feature | Description | Stories |
|---|---|---|---|
| F1 | Camera layout editor | Place cameras and sensors on a 2D community map; mark links and walking times | US-1 |
| F2 | Scenario simulation and event stream | Two scripted scenarios replayed as one event stream: an unfamiliar vehicle repeatedly in residential lanes in the early evening; a person moving along a camera chain toward houses at night. Detection is replaced by scripted events | US-2 |
| F3 | Cross-camera path linking | Use camera-graph space and time limits to join anonymous tracks into one path; IDs expire | US-4, US-8 |
| F4 | Anomaly rules | Path-based, human-defined rules: after-hours entry, loitering, off-route movement | US-3, US-6 |
| F5 | Alert routing and next-camera suggestion | Send the alert to the nearest guard and suggest the next camera to check | US-3, US-4 |
| F6 | Guard alert screen | One screen with the alert, map, suggested camera and reason; guard can confirm or dismiss | US-3, US-4, US-5 |
| F7 | Agent layer | A general-purpose agent, served through Google Vertex AI, reasons over event sequences, ranks alert severity, explains why, and writes the incident timeline | US-5, US-6, US-7 |
| F8 | Evaluation script | Per scenario: time to first alert, next-camera accuracy, false alerts, timeline match, against a guards-check-screens-in-turn baseline | US-2 |

### Should (added before 11 Nov final submission)

| ID | Feature | Description | Stories |
|---|---|---|---|
| F9 | Offline camera fallback | When a key camera is offline, reason through neighbouring nodes and mark the blind spot; adds a third scenario | US-10 |
| F10 | Public video ingestion demo | Run a licensed public city video through an off-the-shelf detector to feed real events into the F2 stream | US-11 |
| F11 | Post-incident path query | Enter a time window; get one anonymous cross-camera path and its timeline | US-9 |
| F12 | Retention setting and audit log | Configurable data retention; log who viewed what | US-8 |
| F13 | Learned normal-movement baseline | Learn typical movement per camera and time of day from public video and simulated data, and use it to tune F4 thresholds | US-12 |

### Won't (not in this version)

| ID | Not building | Reason |
|---|---|---|
| W1 | Facial or identity recognition | Privacy risk; cross-camera person matching is also an open research problem. The design uses layout and paths instead |
| W2 | Suspect labelling and personal intent prediction | The system sees behaviour, cannot verify intent, and could mislabel people |
| W3 | Licence plate recognition | Creates personally identifiable data, beyond this version's privacy boundary |
| W4 | Connection to real CCTV or VMS | No usable real system or permission at prototype stage |
| W5 | Automatic police reports or dispatch | Responses stay a human decision |
| W6 | Native mobile app | A web interface is enough for the demo |
| W7 | Multi-township deployment | Prove it in one simulated community; Scalable is argued in the pitch only |
| W8 | 3D layout view | Sky confirmed 2D is enough; 3D is not required |

## 5. Acceptance Criteria

Each criterion is written so it can be checked in a demo or by script. Numeric targets are suggestions for the team to confirm (section 7).

### F1 Camera layout editor

- A user can add, move and delete cameras and sensors on the 2D map and set their facing direction.
- A user can link two nodes and enter an expected walking time; the system rejects self-links and duplicate links.
- A layout can be saved to a file and reloaded, and is identical after loading.
- A layout of about 20 nodes can be built in 5 minutes.

### F2 Scenario simulation and event stream

- Both scenarios start, pause and reset with one action; repeated runs give the same event sequence.
- Each event holds time, camera ID, type and an anonymous object ID, and nothing that identifies a person.
- Events enter the stream in one format; F3 to F7 read only from the stream.

### F3 Cross-camera path linking

- If an object leaves camera A and appears at connected camera B within the link's walking-time window, the two tracks join into one path.
- If it appears outside the window, or at an unconnected camera, the system does not join them and treats it as a new object.
- Anonymous object IDs expire after a set time and cannot be queried afterwards.
- No facial features are used anywhere.

### F4 Anomaly rules

- At least three rules: after-hours entry, loitering beyond a set time in one zone, off-route movement.
- Each rule's thresholds can be changed in configuration without code changes.
- Every anomaly carries the rule name and the events it relied on.
- In both scenarios all target anomalies are caught, and false alerts from normal background activity stay within the F8 target.

### F5 Alert routing and next-camera suggestion

- The alert goes to the on-duty guard with the shortest walking time (from the camera graph) to the event.
- The system names the most likely next camera and lists its basis (distance, walking time, known path).
- With no guard on duty, the alert escalates to the supervisor instead of being lost.

### F6 Guard alert screen

- A new alert appears on screen within 2 seconds, with a notification cue.
- One alert card shows location, triggered rule, severity, suggested next camera and a map highlight.
- A guard can confirm or dismiss with one click and add a one-line reason; the action is recorded in the incident timeline.
- With up to 5 simultaneous alerts, no key information is hidden or needs scrolling.

### F7 Agent layer

- The agent can only read the camera graph, guard roster and event log through defined tools; it cannot access raw video.
- For each alert it returns a severity (high, medium, low) and a reason of at most three sentences.
- After each scenario it writes a time-ordered timeline, and every entry matches a real event in the stream.
- The timeline contains no event missing from the stream; when information is insufficient, the agent says it cannot be determined rather than inventing detail.
- The agent makes no suspect judgement and no inference about identity or intent.

### F8 Evaluation script

- One command runs all scenarios and prints a report in one format.
- The report covers time to first alert, next-camera accuracy, false alerts per camera per night, and timeline match.
- The report also gives the guards-check-screens-in-turn baseline, computed on the same scenarios.

### F9 Offline camera fallback (Should)

- After a camera is marked offline, F3 still infers the path through neighbouring nodes and the screen marks the blind spot.
- The third scenario (key camera offline) runs end to end.

### F10 Public video ingestion demo (Should)

- A public video with clear permission to use produces anonymous events through an off-the-shelf detector, and they enter the F2 stream.
- No identifiable face is stored or shown in the demo.

### F11 Post-incident path query (Should)

- Given a start and end time, the system returns one anonymous path and its timeline for that window.
- The query returns within 10 seconds.

### F12 Retention setting and audit log (Should)

- Retention is configurable; data past retention is deleted automatically and the deletion appears in the log.
- Every query and confirmation is written to an audit log with user, time and target.

### F13 Learned normal-movement baseline (Should)

- The baseline is built from public video and simulated data only, with no identity data.
- Using the baseline lowers false alerts compared with fixed thresholds on the same scenarios, shown in the F8 report.
- Supervisors can still override any learned threshold by hand.

### Cross-feature requirements

| Category | Requirement |
|---|---|
| Privacy | No facial recognition; no real faces in the demo or documents; object IDs anonymous and expiring; follows PDPA notice, purpose, security and deletion principles |
| Performance | Event entering the stream to alert on screen in at most 2 seconds (simulated environment) |
| Explainability | Every alert states the triggered rule and the events it relied on |
| Human in the loop | The system only suggests; guards and supervisors decide the response |
| Reproducibility | All scenarios and evaluation results can be repeated from the same version |
| Demo stability | The 5-minute demo is a recording, so each scenario must run cleanly end to end from a fresh start |

## 6. Non-goals

The Won't list in section 4 names features not built. This section states what the project does not try to achieve, so judges and the team do not misread the scope.

- **Not a system that identifies people.** It does not decide who someone is or whether they are a suspect. It only says that a movement looks unusual and suggests the next camera to check.
- **Not a predictor of personal intent or crime.** It flags anomalies in event sequences, not conclusions about anyone's motive.
- **Not a replacement for guards or police.** It shortens the time to notice and respond; response, reporting and investigation stay with people.
- **Not a replacement for existing cameras or VMS.** It is a layer on top of existing equipment, not new cameras or a new recording system.
- **Not handling real surveillance data in this version.** The prototype uses simulated scenarios and public video with clear permission, and no footage from a real community.
- **Not chasing detector accuracy.** The innovation is the relationships between cameras and event reasoning; object detection uses off-the-shelf models.
- **Not a full commercial plan.** Pricing, procurement and long-term operations appear only briefly in the pitch.

## 7. Open Questions

Still open. Owners and due dates are suggestions for the team to confirm.

| # | Question | Affects | Suggested owner | Due |
|---|---|---|---|---|
| Q1 | Are the targets (next-camera accuracy at least 80%, at most 2 false alerts per camera per night, timeline match at least 90%) reasonable? How should the check-screens-in-turn baseline be modelled? | F8 acceptance | Team | 21 Oct |
| Q2 | Where do scenario parameters (routes, times, walking times) come from? Should they be checked against a real residential layout? | Credibility of F2, F3 | Team | 21 Oct |
| Q3 | How long should data be kept? PDPA sets no fixed period. | F3, F12 | Team | 6 Nov |
| Q4 | Which public city video sources will be used, and do their licence terms allow use in a competition demo? | F10, F13, privacy | Sky | 2 Nov |
| Q5 | How is normal movement learned (model type, training data, how humans override)? Rules stay human-defined first; the learned baseline is Should. | F4, F13 | Team | 6 Nov |
| Q6 | Is Google Vertex AI cost and latency acceptable for the agent layer, and which model is used? | F6 latency target, F7 | Team | 23 Oct |
| Q7 | Interview a security company supervisor to check guard workflow, alert volume they can handle, and what counts as a normal route. | Personas, F4, F5 | Sky | 6 Nov (mentoring week) |
| Q8 | What does the Top 10 pitch format on 14 Nov require beyond the recorded demo? | Demo plan | Team | 28 Oct |

### Decisions already made

| Topic | Decision |
|---|---|
| Layout editor | 2D is enough; 3D is not required and moves to Won't (W8) |
| Data | Use publicly available city camera video from the web |
| Camera ownership and access | The security company holds access and operates the system (to be confirmed by interview) |
| Rules for normal behaviour | Machine learning, with human-defined rules also acceptable |
| Agent platform | Google Vertex AI |
| Demo format | A recording is sufficient; no live demo needed |
| Other hackathons | Focus on Sime Darby for this PRD |
