# CC Task: Add File Logging

## What this is

Add persistent log file output alongside the existing terminal output. Logs go to `data/prod/tir.log`.

## File to modify

`run_server.py`

## Change

Replace the `logging.basicConfig` call with:

```python
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("data/prod/tir.log"),
        ],
    )
```

## Verify

```bash
cd /path/to/Tir
python run_server.py &
sleep 3
cat data/prod/tir.log
```

Should see startup log lines in the file. Kill the server after.

## What NOT to do

- Do NOT change anything else in run_server.py
- Do NOT add log rotation — the file is fine for now
