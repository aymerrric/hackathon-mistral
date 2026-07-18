---
name: access-multiwoz-data
description: Download and load the MultiWOZ 2.2 dialogue dataset (via Salesforce/DialogStudio on Hugging Face) for this project. Use when you need the raw dataset locally to build or test the tree-generation / call-analysis features.
---

# Accessing the MultiWOZ 2.2 dataset

This project uses MultiWOZ 2.2 (task-oriented dialogues) sourced through the
[Salesforce/dialogstudio](https://huggingface.co/datasets/Salesforce/dialogstudio)
dataset on Hugging Face, which is **gated** — every team member needs their
own Hugging Face account, an accepted access request, and a personal token.

## One-time setup (per person)

1. Create a Hugging Face account if you don't have one: https://huggingface.co/join
2. Visit https://huggingface.co/datasets/Salesforce/dialogstudio and accept
   the dataset's terms (button on the page). Access is per-account, not
   per-token — do this before generating a token.
3. Create an access token at https://huggingface.co/settings/tokens (read
   access is enough).
4. In the repo root, create a `.env` file (already gitignored — never commit
   it) with:

   ```
   HF_TOKEN=hf_your_token_here
   ```

5. Install [uv](https://docs.astral.sh/uv/) if you don't have it, then sync
   the root Python environment (this is a separate small uv project from
   `backend/`, just for data tooling):

   ```bash
   uv sync
   ```

## Downloading the dataset

From the repo root:

```bash
set -a; source .env; set +a   # loads HF_TOKEN into the shell (bash/zsh)
uv run python notebooks/scripts/download_multiwoz.py
```

On Windows PowerShell, load the token instead with:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^(.*?)=(.*)$') { Set-Item "env:$($matches[1])" $matches[2] } }
uv run python notebooks/scripts/download_multiwoz.py
```

This saves the dataset (train/validation/test splits, ~300MB) to
`data/multiwoz_2_2/` in Hugging Face `Dataset` format. `data/` is gitignored
— everyone downloads their own local copy rather than committing it.

## Loading it in a notebook or script

```python
from datasets import load_from_disk

dataset = load_from_disk("data/multiwoz_2_2")
print(dataset)
# DatasetDict with train (8437 rows) / validation (1000) / test (1000)
# Each row has: original dialog id, log (turns), dst knowledge,
# intent knowledge, prompt, etc. — see the dataset README for full schema:
# https://github.com/salesforce/DialogStudio/tree/main/task-oriented-dialogues/MULTIWOZ2_2
```

## Notes

- `datasets` is pinned to `<3` in `pyproject.toml` because
  `Salesforce/dialogstudio` uses a legacy loader script that `datasets>=4`
  no longer supports — don't upgrade it without checking this still works.
- A `HF_TOKEN` repo secret also exists in GitHub Actions for CI use, but
  that does **not** grant you personal access to the gated dataset locally —
  each person still needs to accept the terms and use their own token per
  the steps above.
