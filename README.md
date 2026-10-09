# mini-tools

Small, tested command-line utilities for everyday data chores. Standard library only.

| Tool | What it does | Usage |
|---|---|---|
| `csvclean` | Trim cells, snake_case headers (clashing names get `_2`, `_3`; blank ones become `column_N`), drop empty/duplicate rows; `-d ';'` / `--out-delimiter` for non-comma files | `python -m minitools.csvclean in.csv out.csv --dedupe -d ';'` |
| `json2csv` | JSON array of objects (or JSON Lines via `--lines` / `.jsonl`) to CSV; nested keys flattened as `a.b`, missing keys left empty; `--path data.items` unwraps an array inside an API response | `python -m minitools.json2csv in.json out.csv` |
| `datenorm` | Rewrite one CSV date column as ISO `YYYY-MM-DD`; ISO timestamps keep their date part (day-first by default, `--monthfirst` for US dates, `--strict` to fail on unparseable cells) | `python -m minitools.datenorm in.csv out.csv -c date` |
| `dedupe` | Drop duplicate lines while keeping the original order; `-i` ignore case, `-s` ignore surrounding spaces, `--skip-blank`, `--keep-last` to keep the final occurrence, `--only-dupes` to list only repeated lines (with counts under `--stats`), `--stats` | `python -m minitools.dedupe emails.txt -o unique.txt -i -s --stats` |
| `wordfreq` | Line/word/char totals and the most frequent words across one or more files (case-insensitive, Unicode-aware); `--min-length`, `--min-count N` to hide rare words, `--stopwords FILE`, `--encoding cp1252` for non-UTF-8 files (clear error instead of a traceback), `--csv` | `python -m minitools.wordfreq notes.txt -n 10 --min-length 3` |
| `renamer` | Bulk-rename files in one folder with a regex (`\1` groups); dry run by default, `--apply` to rename; refuses the whole batch on name clashes; `--glob`, `-i` | `python -m minitools.renamer photos "^IMG_(\d+)" "trip_\1" --apply` |
| `csvstats` | Per-column profile of a CSV: filled/empty/distinct counts, plus min/max/mean for all-numeric columns (`nan`/`inf`/`1_000` count as text); `-d`, `--decimal-comma`, `--csv` | `python -m minitools.csvstats data.csv -d ";" --decimal-comma` |
| `csvsplit` | Split a CSV into files of N rows (`--rows`) or one file per column value (`--by`), header repeated in each; blank lines skipped, `-d`, `-o outdir`, refuses to overwrite unless `--force` | `python -m minitools.csvsplit sales.csv --by country -o parts` |
| `csvjoin` | Join two CSVs on a key column (inner or `--how left`), one-to-many matches kept, keys trimmed, clashing right columns get `_right`; `--right-key`, `-d`, `-o` refuses to overwrite unless `--force` | `python -m minitools.csvjoin orders.csv customers.csv -k customer_id -o joined.csv` |
| `csvcut` | Keep and reorder (`-c email,id`) or drop (`-x notes`) CSV columns by name; unknown names fail with the list of real headers, short rows padded, quoting preserved; `-d`, `-o`, stdin via `-` | `python -m minitools.csvcut contacts.csv -c email,name -o emails.csv` |
| `csvsort` | Sort CSV rows by one or more columns (`-k country,amount`); all-numeric columns sort as numbers, text case-insensitively, empty cells last even with `-r`; stable, unknown names list the real headers; `-d`, `-o`, stdin via `-` | `python -m minitools.csvsort sales.csv -k country,amount -r -o sorted.csv` |
| `csvfilter` | Keep rows matching conditions like `amount>=100`, `country=NL`, `email~regex` (`=` `!=` `>` `>=` `<` `<=` `~` `!~`); repeat `-w` for AND or add `--any` for OR; numbers compare as numbers, text cells never match `>`/`<`; `-i`, `--count`, `-d`, `-o`, stdin via `-` | `python -m minitools.csvfilter sales.csv -w "country=NL" -w "amount>=100" -o nl_big.csv` |

```bash
python -m pytest
```
