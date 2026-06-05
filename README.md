# Terminal-Bench Trajectory Dataset

This folder contains the Terminal-Bench v2 leaderboard scraper and the collected
balanced trajectory dataset used for analysis.

## Contents

- `collect_tbench_leaderboard.py`: scraper and trajectory downloader.
- `leaderboard_v2.json`: leaderboard submissions, tasks, scores, and
  `has_trajectories` availability flags.
- `trajectory_index_balanced_12.json`: master index for the final collected
  trajectory dataset.
- `trajectories_balanced_12/`: full trajectory JSON files, organized as
  `{scaffold}/{model}/{taskChecksum}_{trialId}.json`.

## Run From This Folder

```powershell
cd "C:\Users\marin\OneDrive\Documentos\Tu Delft\MSc Thesis\terminal_bench_trajectory_work"
..\thesis-agentic-apr-platform\.venv\Scripts\python.exe collect_tbench_leaderboard.py --help
```

## Main Commands

Refresh the leaderboard task metadata:

```powershell
..\thesis-agentic-apr-platform\.venv\Scripts\python.exe collect_tbench_leaderboard.py --output leaderboard_v2.json
```

Check which submissions expose trajectory pages:

```powershell
..\thesis-agentic-apr-platform\.venv\Scripts\python.exe collect_tbench_leaderboard.py --check-trajectory-availability --leaderboard-json leaderboard_v2.json
```

Collect the final balanced sample:

```powershell
..\thesis-agentic-apr-platform\.venv\Scripts\python.exe collect_tbench_leaderboard.py --collect-trajectories --leaderboard-json leaderboard_v2.json --sample-n 12 --strategy balanced --trajectories-dir trajectories_balanced_12 --trajectory-index trajectory_index_balanced_12.json
```

Run a small debug collection:

```powershell
..\thesis-agentic-apr-platform\.venv\Scripts\python.exe collect_tbench_leaderboard.py --collect-trajectories --leaderboard-json leaderboard_v2.json --sample-n 3 --strategy balanced --task-limit 5 --trial-limit 2 --trajectories-dir trajectories_debug --trajectory-index trajectory_index_debug.json
```

## Important Flags

- `--output`: where to write leaderboard metadata.
- `--leaderboard-json`: existing leaderboard file to load for availability
  checks or trajectory collection.
- `--check-trajectory-availability`: fetches one trial page per submission and
  updates `has_trajectories` in the leaderboard file.
- `--collect-trajectories`: downloads task trial pages and full trajectory JSON.
- `--sample-n`: number of submissions to sample.
- `--strategy`: sampling method: `top`, `bottom`, `stratified`, or `balanced`.
  `balanced` samples high/mid/low performers and caps each scaffold at 3 when
  feasible.
- `--trajectories-dir`: output folder for trajectory JSON files.
- `--trajectory-index`: output master index file.
- `--task-limit`: maximum tasks per sampled submission, useful for debugging.
- `--trial-limit`: maximum trials per task, useful for debugging.
- `--availability-limit`: maximum submissions to check in availability mode.
- `--limit`: maximum submissions to fetch when refreshing leaderboard metadata.

## Dataset Index

`trajectory_index_balanced_12.json` is the table of contents for analysis. Each
row contains:

- `scaffold`
- `model`
- `taskName`
- `taskChecksum`
- `trialId`
- `reward`
- `cost`
- `duration`
- `filePath`

Load it with pandas:

```python
import json
import pandas as pd

df = pd.DataFrame(json.load(open("trajectory_index_balanced_12.json")))
print(df.groupby("scaffold")["reward"].agg(["count", "mean"]).round(2))
```
