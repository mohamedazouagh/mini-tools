# mini-tools

Small, tested command-line utilities for everyday data chores. Standard library only.

| Tool | What it does | Usage |
|---|---|---|
| `csvclean` | Trim cells, snake_case headers (clashing names get `_2`, `_3`; blank ones become `column_N`), drop empty/duplicate rows; `-d ';'` / `--out-delimiter` for non-comma files | `python -m minitools.csvclean in.csv out.csv --dedupe -d ';'` |
| `json2csv` | JSON array of objects (or JSON Lines via `--lines` / `.jsonl`) to CSV; nested keys flattened as `a.b`, missing keys left empty; `--path data.items` unwraps an array inside an API response | `python -m minitools.json2csv in.json out.csv` |
| `datenorm` | Rewrite one CSV date column as ISO `YYYY-MM-DD`; ISO timestamps keep their date part (day-first by default, `--monthfirst` for US dates, `--strict` to fail on unparseable cells) | `python -m minitools.datenorm in.csv out.csv -c date` |
| `dedupe` | Drop duplicate lines while keeping the original order; `-i` ignore case, `-s` ignore surrounding spaces, `--skip-blank`, `--keep-last` to keep the final occurrence, `--stats` | `python -m minitools.dedupe emails.txt -o unique.txt -i -s --stats` |
| `wordfreq` | Line/word/char totals and the most frequent words across one or more files (case-insensitive, Unicode-aware); `--min-length`, `--stopwords FILE`, `--csv` | `python -m minitools.wordfreq notes.txt -n 10 --min-length 3` |
| `renamer` | Bulk-rename files in one folder with a regex (`\1` groups); dry run by default, `--apply` to rename; refuses the whole batch on name clashes; `--glob`, `-i` | `python -m minitools.renamer photos "^IMG_(\d+)" "trip_\1" --apply` |
| `csvstats` | Per-column profile of a CSV: filled/empty/distinct counts, plus min/max/mean for all-numeric columns; `-d`, `--decimal-comma`, `--csv` | `python -m minitools.csvstats data.csv -d ";" --decimal-comma` |
| `csvsplit` | Split a CSV into files of N rows (`--rows`) or one file per column value (`--by`), header repeated in each; blank lines skipped, `-d`, `-o outdir`, refuses to overwrite unless `--force` | `python -m minitools.csvsplit sales.csv --by country -o parts` |

```bash
python -m pytest
```
