---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

If the user passes a ticket reference, fetch it from the issue tracker and state its title before starting. If the reference is ambiguous, ask.

Call the Skill tool with "tdd" where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, call the Skill tool with "code-review" to review the work.

Commit your work to the current branch.

If the work came from a ticket and resolves it completely, the PR body contains `Closes #<ticket>` on its own line (GitHub closes the issue on merge; `Fixes #<ticket>` for a bug). Check this before reporting done: never leave it out, and never open the PR without it. If part of the ticket stays open, omit the keyword, say what remains in the PR body, and leave the issue open.
