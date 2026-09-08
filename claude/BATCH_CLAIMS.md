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

### sess-2026-09-08-a · claimed 2026-09-08T00:50Z, rebased 01:0xZ
Ranks 300–333 by market cap, 25 names (the covered ones in that span are skipped):

VMC CNC RMD BIIB JBL CCI PCG ZTS CBOE WTW HAL EXR CFG RDDT IR AEE HPQ DG ON
DTE ATO TDY CTSH VICI CASY

**VMC is BUILT AND VERIFIED but NOT YET IN THE REPO.** The file was produced in a chat
session with no git credentials, where the GitHub connector is the only write channel
and every push costs the full ~58KB of file content inline. It passed the full harness:
60 real monthly closes from digrin's unadjusted Real price column, final chart value
262.63 == header price, P/E 30.94 vs 262.63/8.48 = 30.97, 52-week range contains the
price, two canvases, `node --check` clean. Data as of the **Sep 4, 2026** close;
sha256 `6702e7a5e8108cf7aab15f5bd105e006e44aa6e35bc2e82889188fc24c041510`.
Oki has the file. Whoever runs the batch with the repo attached should commit it as
part of the wave rather than rebuild it — and must still add its index card.

Notes carried into this batch:
- **FISV (rank 330) is NOT in this batch.** Fiserv is already live as
  `reports/fi_analysis.html`. The constituent list now shows the ticker as FISV, so
  this is a rename job — filename, `<title>`, ticker badge and the index card all need
  the treatment MRSH got — not a new report. Logged, not claimed.
- CFG is a regional bank: reuse the COF/USB/PNC metric handling (NIM, ROTCE, CET1,
  efficiency ratio; mark gross margin and current ratio n/m).
- CCI, EXR and VICI are REITs: lead with FFO/AFFO, same n/m marks.
- WTW is a broker, not an underwriter — do not reach for the combined ratio.
- PCG carries wildfire liability and a post-bankruptcy share count; check the history
  before trusting any long-run per-share series.
- Q (rank 357, Qnity Electronics) and VMRK (rank 232, Vivmark Residential) are both
  unfamiliar recent entities. Whoever takes them: verify what they are and where they
  came from before writing. Do not infer a history.

## Findings worth keeping (from the VMC build)

- **The provenance dance is stricter than the docs said.** A URL appearing as a link
  inside an already-fetched page is NOT sufficient provenance — WebFetch still refuses
  it. Only a URL returned by a *search* works. Budget one search per new domain, then
  fetch that domain's pages freely. stockanalysis.com per-ticker pages each needed the
  parent domain surfaced by search first.
- **digrin serves a stale header price but correct monthly closes.** Its VMC page
  header read $275.94 (an Aug 24 close) while the monthly table's September row was
  the correct $262.63. Take the table, ignore the header, and always anchor the final
  point to the stockanalysis quote page.
- **`stockanalysis.com/stocks/<t>/history/` defaults to daily with pagination** and is
  the wrong source for the 5-year chart. Go to digrin.
- **Two bugs were found in the shared verification harness** and are fixed in the copy
  Oki holds: `<head` was matching `<header`, and the array regex assumed `labels:`
  where the house format is `const labels = [`. An older harness would have failed
  every valid report in this batch.

## POOL — released, unclaimed, take freely

Ranks 205–240 (released by sess-2026-09-08-a before any research was done):

NUE PSA CTVA F MRNA CAH FIX KEYS DVN COHR SRE AME NDAQ GRMN STT DAL EW ETR
VMRK BDX XYZ AMP CARR COIN AZO

- COIN is the long-standing held report — no file exists. Needs digrin.com reachable
  for the monthly series, else a sourced alternative. Do not publish a 13-month chart
  under a five-year heading.
- XYZ is Block, Inc. Filename `xyz_analysis.html`.

Ranks 241–299, also unclaimed:

HUM ROK WAB LHX VTR ARES EBAY CIEN VEEV FERG IQV CBRE A MSCI YUM ADM FLEX LYV
WAT DHI ED SYY EL PEG MLM NTAP UAL KVUE KR EXPE TKO KMB HSY IRM STLD WEC EQT
HBAN RJF NTRS

## DONE

_(none yet)_
