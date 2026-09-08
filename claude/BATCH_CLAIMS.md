# Batch claims — concurrency ledger

Multiple Claude sessions work this repo at the same time. Without a shared claim,
every session runs the same market-cap diff, gets the same answer, and writes the
same 25 reports. This file is the lock.

## Protocol

1. `ls reports/*_analysis.html` (or GitHub `get_file_contents` on `reports/`) to get
   the covered set. The repo is the source of truth — not the coverage index, not a
   handoff note, not memory.
2. Fetch a current ranking (`stockanalysis.com/list/sp-500-stocks/`) and diff.
3. **Read this file.** Skip every ticker in an OPEN claim.
4. Append your claim before doing any research. Use `create_or_update_file` with the
   blob SHA you just read — if the write is rejected as a conflict, another session
   claimed in the gap. Re-read, re-diff, re-claim. Do not force.
5. On finish, move your block to DONE and list any ticker you did not publish so it
   returns to the pool.
6. A claim older than 24h with nothing published is stale — take it.

Publishing an already-covered ticker is not a merge conflict, it is silent duplicate
work, so the claim goes in first and the research goes second.

## OPEN

### sess-2026-09-08-a · claimed 2026-09-08T00:50Z
Ranks 205–240 by market cap, 25 names:

NUE PSA CTVA F MRNA CAH FIX KEYS DVN COHR SRE AME NDAQ GRMN STT DAL EW ETR
VMRK BDX XYZ AMP CARR COIN AZO

Notes carried into this batch:
- COIN is the long-standing held report — no file exists. Needs digrin.com reachable
  for the monthly series, else a sourced alternative. Do not publish a 13-month chart
  under a five-year heading.
- VMRK (Vivmark Residential, rank 232) is unfamiliar and recent. Verify what it is and
  where it came from before writing; do not infer a history.
- XYZ is Block, Inc. Filename `xyz_analysis.html`.

## DONE

_(none yet)_
