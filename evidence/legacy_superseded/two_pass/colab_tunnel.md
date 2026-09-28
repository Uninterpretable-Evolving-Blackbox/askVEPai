# Exposing a Colab GPU to the local harness over a tunnel

The pattern that produced the 2026-09-04 numbers: **Ollama runs on Colab, the harness runs on the
laptop**, and a cloudflared quick tunnel carries the model calls between them. Only the LLM traffic
crosses the network; the code, the catalogue and the results stay local.

This is NOT what `colab_eval.md` describes. That one runs everything inside Colab cells off the
**public** repo, which lacks `real_testset_8.json` and the raised thinking-token cap — so the
attribution jobs fail there exactly as they did on 2026-09-04. Use this file for those jobs.

**Runtime → Change runtime type → L4 GPU.** `gemma4:26b` is ~16 GB of weights; a T4's 16 GB leaves
nothing over.

---

## Cell 1 — install Ollama and cloudflared

`zstd` first: Colab's image lacks it and the Ollama installer fails with "This version requires zstd
for extraction", which then cascades into `nohup: failed to run command 'ollama'`.

```python
!apt-get -qq update && apt-get -qq install -y zstd pciutils
!curl -fsSL https://ollama.com/install.sh | sh
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
!dpkg -i cloudflared-linux-amd64.deb && cloudflared --version
```

## Cell 2 — start the server with the three settings that matter

`!ollama serve &` does not survive the cell; use `Popen`. The environment carries three things:

| var | why |
|---|---|
| `OLLAMA_CONTEXT_LENGTH=16384` | the default is 4096 and the prompt is ~9,700 tokens. **Measured: enable-F1 20% at 4096, 65% at 16384.** The run completes either way and the number is silently wrong |
| `OLLAMA_HOST=0.0.0.0:11434` | the default binds loopback, which the tunnel cannot reach |
| `OLLAMA_ORIGINS=*` | a tunneled request arrives with a `trycloudflare.com` Host header |

```python
import os, subprocess, time, urllib.request
env = dict(os.environ,
           OLLAMA_CONTEXT_LENGTH="16384",
           OLLAMA_HOST="0.0.0.0:11434",
           OLLAMA_ORIGINS="*")
subprocess.Popen(["ollama", "serve"], env=env,
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

## Cell 3 — pull the model, then verify it is on the GPU at full context

~16 GB over Google's network. `ollama ps` shows nothing until a model is resident, so load it first.

```python
!ollama pull gemma4:26b
!ollama run gemma4:26b "say ok" > /dev/null 2>&1
!ollama ps
```

**Read the output before continuing.** `CONTEXT` must be `16384` and `PROCESSOR` must be `100% GPU`.
Anything less than 100% GPU means part of the model spilled to CPU and the run will take hours.

## Cell 4 — open the tunnel and print the URL

```python
import subprocess, time, re, urllib.request
subprocess.Popen(["cloudflared", "tunnel", "--url", "http://localhost:11434", "--no-autoupdate"],
                 stdout=open("/tmp/cf.log", "w"), stderr=subprocess.STDOUT)
url = None
for i in range(60):
    time.sleep(1)
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", open("/tmp/cf.log").read())
    if m:
        url = m.group(0); break
if not url:
    print(open("/tmp/cf.log").read()[-2000:])
else:
    code = urllib.request.urlopen(url + "/api/tags", timeout=30).status
    print(f"\n  {url}\n\n  /api/tags through the tunnel -> HTTP {code} (200 means hand this over)")
```

The end-to-end check matters: it proves the tunnel forwards `/api/` paths, which is what the harness
uses, rather than only answering on the root.

## Then, locally

Hand over the bare root URL — no trailing slash, no `/v1`. The script appends `/v1` for the compat
client and derives `/api/chat` for the native one, both over the same tunnel.

```bash
bash work/harness/done/resume_attribution.sh https://<the-url>.trycloudflare.com
```

---

## Things that will bite

- **The URL is single-use.** A quick tunnel dies with the Colab session and cannot be revived; a new
  session means a new URL. HTTP 530 mid-run means the tunnel dropped, which is what killed jobs 3 and
  4 on 2026-09-04.
- **Idle disconnect.** Colab reclaims an idle runtime. Keep the tab open and visible for the ~45 min.
- **Leave `VEP_KEEP_ALIVE` unset.** The default (`-1`, resident forever) is right on a dedicated GPU;
  it is only wrong on a laptop that is also doing other work.
- **Colab is CUDA; the pre-2026-09-04 figures are Metal (M5 Max).** Quote the hardware with the number
  and re-run both arms of any comparison on the same machine.
