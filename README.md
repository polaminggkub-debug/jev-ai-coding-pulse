# Jev Reddit Pulse

Open `pulse.html` directly in a browser. It embeds its data, styles, and vanilla
JavaScript and makes no external requests. Source links open Reddit only when
clicked. Family rows start collapsed; use a row or **Expand all model details**
to inspect versions, quotes, and threads. Search filters the model choices, and
selecting a chip isolates that family or version, including rare models.

## Offline build and checks

Python 3's standard library is sufficient. Run from the repository root:

```sh
python3 -m unittest discover -s pipeline
python3 pipeline/build.py
```

An additional dependency-free JavaScript interaction harness can run with Node:

```sh
node pipeline/test_pulse_ui.js
```

The builder reads `data/labeled.json`. Legacy rows without a `version` field are
backfilled in memory from comment text, then the thread title. Explicitly unknown
versions remain `null`; unknown mentions count toward their family. Opinion bars
exclude `no_opinion` labels. Best-right-now picks require 20 opinions and rank by
(praise − complaint) / opinions, breaking ties by opinion count then name.
Most-talked-about counts include neutral mentions. These are Reddit sentiment
summaries, not model benchmarks.

## Future incremental collection

`pipeline/fetch.py` collects new data from Arctic Shift; `pipeline/classify.py`
uses Jev via OpenRouter. Both resolve paths relative to this repository,
regardless of the current directory. **Neither is needed for the offline demo.**

The classifier seeds `data/classify_cache.json` from existing labeled judgments
and persists successful judgments by `(comment_id, subject)`. Post IDs carry a
`post:` prefix. Unseen pairs alone require decisions and `OPENROUTER_API_KEY`;
unchanged pairs reuse labels and refresh scores. Failed decisions remain retryable.
