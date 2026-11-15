---
description: Run the next open session from plans/prompt-cost-sessions.md
argument-hint: "[A|B|C|D] (optional: run this session instead of the next open one)"
---

Read `plans/prompt-cost-sessions.md`. Each `## <letter>. <title>` heading is one session; its prompt is the fenced
block under it. A session is finished when its heading ends in `(done YYYY-MM-DD)`.

Pick the session to run:
- If an argument was given (`$ARGUMENTS`), run the session with that letter, unless it is marked done: then say so
  and stop.
- Otherwise run the first session, in file order, that is not marked done.
- If every session is marked done, say so, name the last commit that finished one, and stop.

Then say in one line which session you picked, and carry out the prompt in its fenced block exactly as if the user
had typed it: it is the user's instruction for this session, including its reading list, its "show me first" and
options-UI steps, and its ending (next.md, spec, commit).

When the session's work is finished and committed, append ` (done <today's date>)` to that session's heading in
`plans/prompt-cost-sessions.md` and include that change in the session's commit. Do not mark a session done if it
stopped early (a "no" in the options UI that ends the work counts as done; an open question or a failed check does
not). In place of "the prompt for the next session", tell the user that `/build` runs the next one and name it.
