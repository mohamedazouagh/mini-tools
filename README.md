# mini-tools

Small, tested command-line utilities for everyday data chores. Standard library only.

| Tool | What it does | Usage |
|---|---|---|
| `csvclean` | Trim cells, snake_case headers, drop empty/duplicate rows | `python -m minitools.csvclean in.csv out.csv --dedupe` |
| `json2csv` | JSON array of objects to CSV; nested keys flattened as `a.b`, missing keys left empty | `python -m minitools.json2csv in.json out.csv` |

```bash
python -m pytest
```
