# ChatGPT Transcript Fidelity Gap

status: OBSERVED_AND_REPAIRED_AT_POLICY_LEVEL
observed: 2026-09-03
class: PROVENANCE_FAILURE / FALSE_FIDELITY_RISK

## Symptom

A discussion archive may be stored under a path or filename containing `fulltext` while its own header or body states that user quotations are selective and the assistant trajectory was compactly reconstructed. Other recovery records may come from context summaries, structured memory, or pointers rather than a source transcript.

## Root cause

The workflow conflated three different objects:

1. a durable summary of what happened;
2. a direct-source reconstruction preserving selected quotations and reasoning structure;
3. an exact message-level transcript / provider conversation graph.

Model context was treated as if it were a queryable archival message store. It is not.

## Discriminating probe

Before assigning transcript fidelity, ask:

- Is there an exact source artifact containing the message text?
- Is that source provider export/raw graph, exact foreground text, or a derived reconstruction?
- Can the claimed message set be enumerated from that source without filling gaps from memory?
- Are omitted/unknown turns explicitly represented as unknown rather than silently reconstructed?

If any required answer is negative, do not label the record complete/verbatim.

## Repair

- Use `operations/CHATGPT_CONVERSATION_ARCHIVE.md` fidelity classes.
- Acquire historical source from supported official Data Export.
- Mirror important active conversations forward into private storage while exact text is present.
- Reconcile historical archives against the exported conversation source.
- Rename/downgrade misleading `fulltext` records or annotate them with exact source limitations.

## Non-repair

Do not repair an unavailable historical transcript by generating plausible missing assistant text, synthesizing message order from summaries, or treating a nested discussion tree as the raw transcript.

## Promotion lesson

Conversation text is volatile source data. Preserve first; structure and summarize second. Source acquisition and semantic synthesis must remain separate stages.
