# How the Requirements Changed

*Position at 5 November 2026, for the Principal Investigator.*

## Summary

The platform now produces three reports from two sources that are never mixed. Corporation data feeds the corporation report (A) and the minister report (B), both unverified and in the Ministry's existing formats; Survey123, the tool field staff use to record incidents, is the verified source for a new report (C). The direction has been from a flexible design to a simpler, fixed one built around documents the Ministry already uses. Throughout, reported figures come from stored data and are never calculated by the LLM (the AI text model).

## Timeline of significant changes

1. **Mid-July 2026: starting concept.** Survey123 was the only source. The LLM wrote prose around computed figures, and an automatic check matched each figure to its source. *Who: not recorded.*
2. **16-17 July: editable templates, pluggable sources.** Templates could change without a new software release, and data sources could plug in, with a future larger LLM in mind. *Who: the technical advisor.* **Reversed 5 November:** templates are files again, and there are two fixed sources. *Who: the developer, with the stakeholder giving feedback; the advisor's view is not recorded.*
3. **18-27 July: structured entry replaces documents.** Corporations sent situation reports (status reports on an event) as PDF or Word files in no fixed format, plus WhatsApp updates, and the DMU re-typed them. Parsing these with the LLM was rejected as a risk of invented numbers, so corporations would upload spreadsheets. Corporation figures were ranked as authoritative and Survey123 as raw corroboration. *Who: ranking recorded as stakeholder input; spreadsheet design by the team.*
4. **18 August to 5 November: WhatsApp intake built, then dropped.** The DMU could turn exported chats into draft records, with an "hour briefing" added in September. It was dropped (decided around late October) because corporation capture removes the reason for WhatsApp. *Who: drop agreed with the stakeholder; origin not recorded.*
5. **19 August: chat-based capture.** Officers type into a conversation, the LLM structures it, and the officer corrects and files the records. Spreadsheets became secondary. *Who: the team, as far as sources show.*
6. **8-9 September: login added; enforced 5 November.** Users had simply declared who they were. The November work found login was not required on all data; now it is. *Who: the team.*
7. **9 September: quality indicators added.** Reports were scored against quality targets. The scores came off the main dashboard on 5 November and remain on a separate page. *Who: unclear.*
8. **Around late October to 5 November: stakeholder examples become the baseline.** Three stakeholder reports (two corporation, one minister) became the quality standard for A and B. They contain no generated prose, so the LLM was removed from A and B, staying for capture and C. The DMU also gained a table of all corporation incidents and logs. *Who: examples from the stakeholder; changes decided by the developer.*
9. **2-5 November: Survey123 becomes the verified source.** A stakeholder test upload showed "zero incidents" because the only available report used corporation filings, and none existed. The data was fine (719 incidents, 1 January to 2 November). The stakeholder then confirmed field staff verify data before upload, which reversed the ranking in entry 3 and produced the three-report model. C is new, has no baseline yet, and may grow into wider Ministry reporting. From 5 November, a Survey123 file with any row not marked Validated is rejected whole. *Who: the stakeholder.*

## How key requirements evolved

| Requirement | Original | Intermediate | Today |
|---|---|---|---|
| How corporations submit data | PDF or Word plus WhatsApp; DMU re-types | Spreadsheet upload | Chat-based capture; spreadsheets as alternative |
| Role of Survey123 | Only source in first build | Raw, unverified corroboration | Verified source for its own reports |
| Role of the LLM | Prose around figures in all reports | Also extracts records from chat and WhatsApp | Capture and report C only |
| Minister report content | Narrative from Survey123 figures | Corporation sections plus labelled Survey123 figures | 2023 format; no generated prose or Survey123 figures |
| WhatsApp | Informal channel outside the system | Built in (August, September) | Removed |
| Who can change report templates | Developer, in files | Editable in the system, with an admin page | Developer, in files, with stakeholder feedback |
| Access control | None; users picked who they were | Login added, not required on all data | Login required on all data |

## Still open

- **Report C:** what should it contain, and what other reports does the Ministry need?
- **Survey123 data quality:** "verified" means field staff checked the records, but the data has known problems: some event dates are impossible (as old as 1902), large households are undercounted, and shelter relocations are not counted. How to handle these is undecided.
- **Direct Survey123 link, an API (planned, not built):** who owns the data, and can the project get access?
- **Sending corporation incidents into Survey123 (possible future step):** what goes, how often, and which version wins a conflict?
- **Personal details:** one corporation's register lists names and phone numbers, which this system strips. Must they be carried, and is that permitted?
- **Report B:** should it carry incident counts or a short generated opening, and does it cover a date window or a national event named by the DMU?

*Status: all of the changes above are merged into the main version.*
