# Running the evals on Colab

Paste these as separate cells. **First set Runtime → Change runtime type → GPU (T4 or better).**

The three errors a first attempt hits, and why:

| error | cause | fix |
|---|---|---|
| `could not read Username for 'https://github.com'` | `askVEPai-work` is **private** | clone the **public** `askVEPai` instead — it carries `vep_ai_demo/` flat-copied, so the nested-repo problem disappears too |
| `This version requires zstd for extraction` | Colab's image has no `zstd`; the Ollama installer needs it | `apt-get install -y zstd` first |
| `nohup: failed to run command 'ollama'` | cascade from the failed install | fixed by the above |

---

## Cell 1 — install

```python
!apt-get -qq update && apt-get -qq install -y zstd
!curl -fsSL https://ollama.com/install.sh | sh
!pip install -q openai
```

## Cell 2 — start the server (background, and wait for it)

`!nohup ollama serve &` does not survive the cell. Use Popen:

```python
import subprocess, time, urllib.request
subprocess.Popen(["ollama", "serve"],
                 stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
for i in range(60):
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        print(f"ollama up after {i}s"); break
    except Exception:
        time.sleep(1)
else:
    print(open("/tmp/ollama.log").read()[-2000:])
```

## Cell 3 — pull the model (~16 GB, on Google's network, not yours)

```python
!ollama pull gemma4:26b
!ollama list
```

## Cell 4 — get the code

Public repo, no token needed. It includes `vep_ai_demo/` as a flat copy.

```python
!git clone -q https://github.com/Uninterpretable-Evolving-Blackbox/askVEPai.git
%cd askVEPai
!ls vep_ai_demo/vep_assistant.py work/generation/candidates/iced.json
```

## Cell 5 — smoke test before the real run

Two rows, one seed. If this prints a table, everything downstream is mechanical.

```python
import os, json
os.environ["VEP_OPTIONS_FILE"] = "/content/askVEPai/work/vep_options_expanded.json"
rows = json.load(open("work/generation/candidates/iced.json"))
json.dump(rows[:2], open("/tmp/subset2.json", "w"))

!VEP_OPTIONS_FILE=$VEP_OPTIONS_FILE python work/harness/exp/eval_factor_set.py \
    --set /tmp/subset2.json --model gemma4:26b --factor-model gemma4:26b \
    --factors inferred --gold live --runs 1 --concurrency 1
```

`VEP_OPTIONS_FILE` must be exported: the published harness reads it with a bare
`os.environ[...]` and dies on `KeyError` without it.

## Cell 6 — the real runs

Expect ~35 min for the first, ~75 min for the attribution arms.

```python
# 1. the headline: enable-F1 on the live gold, 3 seeds
!VEP_OPTIONS_FILE=$VEP_OPTIONS_FILE python work/harness/exp/eval_factor_set.py \
    --set work/generation/candidates/iced.json --model gemma4:26b \
    --factor-model gemma4:26b --factors inferred --gold live \
    --runs 3 --concurrency 1 --json /content/enable_f1_live.json

# 2. the decomposition arms (same command, --factors swapped)
!VEP_OPTIONS_FILE=$VEP_OPTIONS_FILE python work/harness/exp/eval_factor_set.py \
    --set work/generation/candidates/iced.json --model gemma4:26b \
    --factors oracle --gold live --runs 3 --concurrency 1 \
    --json /content/enable_f1_oracle.json
```

## Cell 7 — save the results off the VM

Colab discards everything on disconnect.

```python
from google.colab import files
files.download("/content/enable_f1_live.json")
files.download("/content/enable_f1_oracle.json")
```

---

## Things that will bite

- **`--concurrency 1` is not optional.** temp=0 is not deterministic under concurrency on a
  MoE stack; the project pins concurrency 1 + fixed seed for exactly this reason.
- **Leave `VEP_KEEP_ALIVE` unset.** The default (`-1`, resident forever) is right on a dedicated
  GPU. Only set it on a shared laptop.
- **Colab is CUDA; every published figure is Metal (M5 Max).** A re-run there is internally
  reproducible but not directly comparable to `89.5%`. Re-run both arms of any comparison on the
  same machine, and record which.
- **Idle disconnect.** Keep the tab alive during the ~35 min run.
- The public clone lags the private working tree: it lacks the preflight guard that catches
  Ollama being down mid-run, which is why cell 5 exists.
