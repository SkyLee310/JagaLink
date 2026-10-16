# Early-Warning Safety Network for Township Communities — Problem Statement

> Markdown transcription of `docs/SDP_Hackathon_Problem_Statement.pdf` (Draft v1, 16 Oct 2026).
> This file is the working copy agents read; the PDF is the frozen original.

University Hackathon 2026 · Sime Darby Property · Township of Tomorrow

| Theme | Focus area | Setting |
|---|---|---|
| PEOPLE | Safety & Security | Guarded residential communities |

## 1. The problem

In guarded residential communities, CCTV cameras work as isolated feeds. A small number of outsourced guards cannot watch every screen all the time, so unusual movement across the community is usually noticed only after a break-in has happened. Police then review footage camera by camera to reconstruct what took place. Burglary is infrequent within any single community, but each case is serious, and by the time it is noticed the offender has already moved on.

## 2. Why it matters: evidence

| Finding | Ref. |
|---|---|
| Property crime made up 47,188 of the 58,255 crimes reported in Malaysia in 2024 (about 81%). House break-in and theft accounted for 11,334 cases, and 77.6% of them happened at night. | [1] |
| Guarded does not mean safe. In one gated community in Subang Jaya, six houses were burgled within five months. In one incident, two outside cars were reportedly in the residents' lane for over an hour without being flagged, and the gate CCTV and central monitoring system were reported as not working. | [2] |
| In another case in the same area, burglars arrived in luxury cars around 7pm, were let in by guards, and cased houses. Police could only start by examining CCTV footage after the fact. | [3] |
| Human monitoring has limits. A research review cites a 1998 survey in which 82% of CCTV operators were confident monitoring up to 16 screens, while half said four screens was the most they could comfortably monitor. It concludes that efficient search for crime across many scenes is likely to be poor. | [4] |
| Following a person across several cameras is still an open research problem, because of occlusion and changes in appearance. A practical system should therefore rely on spatial layout and movement paths, not on recognising faces. | [5] |
| A break-in needs a motivated offender, a suitable target and no capable guardian. The gap in today's setup is the guardian: nobody is continuously watching the whole network. | [6] |

National figures are used because no township-level data was found publicly. See section 9 for what is still to be validated.

## 3. Who is affected

- **Primary users (decide, buy, operate):** property management companies and the outsourced security teams who run the guardhouse and patrols.
- **Beneficiaries:** residents, who pay for security and expect problems to be caught early.
- **Secondary:** police, who need a faster way to reconstruct events after an incident.

## 4. How might we

How might we help security teams see and follow unusual movement across a township's camera network as it happens, so that response begins before an incident escalates?

## 5. What is missing today

Each camera is viewed or analysed on its own. No part of the current setup understands how cameras relate to each other in space, so no one can say that movement seen at camera A is now heading toward camera D. Guards at posts see only what is in front of them, and everything else depends on someone watching a wall of screens.

## 6. Direction being explored

Model the community's cameras and sensors as a connected network on a 3D layout that the operator can arrange. Anonymous movement paths and unusual events (for example entry after hours, loitering, or movement that does not match normal routes) travel across that network. The system alerts the nearest guard and suggests which camera to look at next. The same network also lets police and guards trace a movement path quickly after an incident.

## 7. Success measures

- Time from the first unusual event to the alert reaching a guard.
- False alerts per camera per night, compared with a guards-watching-screens baseline.
- Time to reconstruct a movement path across cameras after an incident.

Baselines will be measured in a simulated community and, if possible, in a one-community pilot.

## 8. Design boundaries (privacy by design)

- No facial recognition. Movement is tracked as anonymous paths with IDs that expire.
- The system flags behaviour, not identity. Humans decide what to do with an alert.
- Data stays with the property management company as the data user. Under Malaysia's PDPA, CCTV footage is personal data when a person can be identified, so notice, purpose limitation, security and deletion apply [7]. A 2019 review noted the Act sets no fixed retention period [8], so retention will be short and configurable.

## 9. Still to validate before submission

- How many cameras and guards a typical SDP township community has, and who owns the camera systems.
- How often serious incidents occur in comparable communities. Public sources give national figures only.
- How long police currently take to review footage after an incident. No public source was found for this.
- One interview with a guard supervisor or property manager to confirm the problem and the alert workflow.

## Sources

1. Department of Statistics Malaysia, *Crime Statistics Malaysia 2025* (2024 data), released 16 Oct 2025. dosm.gov.my/portal-main/release-content/crime-statistics-malaysia-2025 ; case counts from dosm.gov.my/uploads/release-content/file_20251016085554.pdf
2. EdgeProp / The Star, "USJ Heights residents living in fear despite paying for security facilities". edgeprop.my/content/1420819/usj-heights-residents-living-fear-despite-paying-security-facilities
3. New Straits Times, "Burglars use luxury cars to fool guards into letting them into gated communities in Subang Jaya", 2018. nst.com.my/news/crime-courts/2018/08/396789
4. Frontiers in Human Neuroscience, "Looking for trouble: a description of oculomotor search in CCTV operators", 2013. frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2013.00615/full
5. Amosa et al., "Multi-camera multi-object tracking: a review of current trends and future advances", *Neurocomputing* 552, 2023. khub.utp.edu.my/scholars/18183/
6. StarProperty, "Reducing the potential of a break-in" (criminology expert interview). starproperty.my/news/featured-news/reducing-the-potential-of-a-break-in/107950
7. The Rakyat Post, "PDPA: You can be fined for sharing a CCTV clip online", 26 Sep 2025. therakyatpost.com/news/malaysia/2025/09/26/pdpa-you-can-be-fined-for-sharing-a-cctv-clip-online/
8. Malaysiakini, "Malaysia ranks '5th worst' in privacy study", 2019. malaysiakini.com/news/496024
