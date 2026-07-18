# test-data

A small, git-tracked sample of the MultiWOZ 2.2 training data (`data/multiwoz_2_2/train`, which is gitignored in full) so it's easy to see the shape of the data without pulling the full dataset.

- `sample_dialogues.json` — the first 5 dialogues from the train split, exported as plain JSON.

Each dialogue includes the full turn-by-turn log (user utterance, system response, dialog state tracking, intents) plus the external knowledge (DB results) available at that point in the conversation.

Regenerate with:

```
uv run python -c "
from datasets import load_from_disk
import json
ds = load_from_disk('data/multiwoz_2_2/train')
json.dump(ds.select(range(5)).to_list(), open('test-data/sample_dialogues.json', 'w'), indent=2, ensure_ascii=False)
"
```
