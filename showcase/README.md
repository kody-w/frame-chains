# Ten-frame showcase loop

This directory is produced as one complete ten-frame loop.

Each numbered frame is built and committed in its own Git worktree and branch.
The integration branch merges every frame commit without squashing, then adds
the catalog, shared gate, and merge ledger. A frame is not considered complete
until its positive path and deliberate failure path both pass in the browser.

The shared acceptance command is:

```sh
npm run showcase:check
```

`FRAME-LOOP.json` records the final branch and commit incorporated for each
frame so the integration can be audited for omissions.
