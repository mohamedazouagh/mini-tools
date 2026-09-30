# mini-tools

Small, tested command-line utilities for everyday data chores. Standard library only.

| Tool | What it does | Usage |
|---|---|---|
| `csvclean` | Trim cells, snake_case headers, drop empty/duplicate rows; `-d ';'` / `--out-delimiter` for non-comma files | `python -m minitools.csvclean in.csv out.csv --dedupe -d ';'` |
| `json2csv` | JSON array of objects (or JSON Lines via `--lines` / `.jsonl`) to CSV; nested keys flattened as `a.b`, missing keys left empty | `python -m minitools.json2csv in.json out.csv` |
| `datenorm` | Rewrite one CSV date column as ISO `YYYY-MM-DD` (day-first by default, `--monthfirst` for US dates, `--strict` to fail on unparseable cells) | `python -m minitools.datenorm in.csv out.csv -c date` |

```bash
python -m pytest
```
