import sys, subprocess
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "voxcpm==2.0.3", "gradio", "soundfile", "numpy", "pynacl"])

import os, re, uuid, time, math, base64, hashlib, threading, datetime
import urllib.request, urllib.parse
import numpy as np
import gradio as gr
import soundfile as sf
from nacl.signing import VerifyKey
from voxcpm import VoxCPM

# ====== ဒီနေရာတွေကို ပြင်ပါ ======
PUBLIC_KEY = "IhTp+Sk042q9A1Oa04ifQFEWbUcBKv1AE2ZkwBKCawg="
REPO_RAW = "https://raw.githubusercontent.com/kolinaungkolin123-cmyk/On3---Voice-Clone-/main"
TRACKER_URL = ""   # Apps Script ရဲ့ /exec လင့် (မထည့်သေးရင် ဒီအတိုင်းထား)
# =================================

# ---------- Key ----------
def left_text(secs):
    if secs <= 0: return ""
    if secs < 3600: return f"{max(1, math.ceil(secs / 60))} မိနစ်"
    if secs <= 86400: return f"{math.ceil(secs / 3600)} နာရီ"      # ၁ ရက်အောက် → နာရီ
    return f"{math.ceil(secs / 86400)} ရက်"                         # ၂ ရက်ကျော် → ရက်

def check_key(key):
    try:
        pre, exp, rid, sig = (key or "").strip().split(".")
        if pre != "VIP": raise ValueError
        sig = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        VerifyKey(base64.b64decode(PUBLIC_KEY)).verify(f"{pre}.{exp}.{rid}".encode(), sig)
        if len(exp) == 8:      # Key အဟောင်း (ရက်စွဲ)
            end = datetime.datetime.strptime(exp, "%Y%m%d").replace(
                hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc).timestamp()
        else:                  # Key အသစ် (စက္ကန့်)
            end = float(int(exp))
    except Exception:
        return False, "Key မှားနေပါသည်", ""
    try:
        bad = urllib.request.urlopen(
            f"{REPO_RAW}/revoked.txt?t={int(time.time())}", timeout=10).read().decode().split()
        if rid in bad: return False, "Key ကို ပိတ်ထားပါသည်", rid
    except Exception:
        pass
    secs = end - time.time()
    if secs <= 0: return False, "Key သက်တမ်းကုန်သွားပါပြီ", rid
    return True, f"{left_text(secs)} ကျန်သည်", rid

# ---------- Tracker ----------
def _send(params):
    if not TRACKER_URL: return
    def run():
        try:
            urllib.request.urlopen(TRACKER_URL + "?" + urllib.parse.urlencode(params),
                                   timeout=8).read()
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()

def who(request):
    try:
        h = request.headers
        ip = (h.get("x-forwarded-for") or h.get("x-real-ip") or request.client.host or "")
        ip = ip.split(",")[0].strip()
        sid = request.session_hash or ""
    except Exception:
        ip, sid = "", ""
    return sid, hashlib.sha256(ip.encode()).hexdigest()[:10]

def rid_of(key):
    p = (key or "").split(".")
    return p[2] if len(p) >= 3 else ""

def track_visit(request: gr.Request):
    sid, ip = who(request)
    _send({"action": "visit", "sid": sid, "ip": ip, "k": ""})

def heartbeat(key, request: gr.Request):
    sid, ip = who(request)
    _send({"action": "ping", "sid": sid, "ip": ip, "k": rid_of(key)})

# ---------- Model ----------
print("⏳ VoxCPM2 Model ဆွဲတင်နေပါသည်...")
try:
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False)
except TypeError:
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
SR = model.tts_model.sample_rate
os.makedirs("work", exist_ok=True)

STEPS = ["Key စစ်ဆေးခြင်း", "စာကို အပိုင်းခွဲခြင်း",
         "Clone လုပ်ပြီး အသံထုတ်ခြင်း", "ပြီးစီးပါပြီ"]

def render(states, details=None):
    details = details or {}
    rows = ""
    for i, (name, st) in enumerate(zip(STEPS, states)):
        icon = {"done": "<span class='ic ok'>✓</span>", "run": "<span class='spin'></span>",
                "err": "<span class='ic bad'>✗</span>", "wait": "<span class='ic wt'>○</span>"}[st]
        d = f" — {details[i]}" if i in details else ""
        rows += f"<div class='row'>{icon}<span>{i+1}. {name}{d}</span></div>"
    return f"<div class='steps'>{rows}</div>"

IDLE = render(["wait"] * 4)

CSS = """
:root, .gradio-container, .dark {
  --body-background-fill:#000; --background-fill-primary:#000;
  --background-fill-secondary:#0b0b0b; --block-background-fill:rgba(255,255,255,.05);
  --panel-background-fill:rgba(255,255,255,.05);
  --body-text-color:#fff; --body-text-color-subdued:#aaa;
  --block-label-text-color:#fff; --block-title-text-color:#fff; --block-info-text-color:#aaa;
  --input-background-fill:rgba(255,255,255,.07); --input-border-color:rgba(255,255,255,.14);
  --border-color-primary:rgba(255,255,255,.12); --block-border-color:rgba(255,255,255,.12);
  --color-accent:#ec4899;
}
body, .gradio-container {background:#000 !important;}
*, label span, .prose, .prose *, h1, h2, h3, p, textarea, input {color:#fff !important;}
::placeholder {color:#777 !important;}
.block, .form, .panel {background:rgba(255,255,255,.05) !important;
  border-color:rgba(255,255,255,.12) !important;}
textarea, input, select {background:rgba(255,255,255,.07) !important;}
ul.options, .options {background:#111 !important;}
.toast-body, .toast-wrap {background:#1a1a1a !important;}
button.btn {background:linear-gradient(90deg,#ec4899,#3b82f6) !important;
  border:none !important; font-weight:700; font-size:18px !important;}
button.back {background:rgba(255,255,255,.08) !important;
  border:1px solid rgba(255,255,255,.18) !important;}
.hide {display:none !important;}
.badge {padding:10px 14px; border-radius:10px; background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.12); margin-bottom:8px;}
.steps {border:2px solid #ec4899; border-radius:12px; padding:14px;
  background:rgba(255,255,255,.05);}
.row {display:flex; align-items:center; gap:12px; font-size:17px; padding:6px 0;}
.ic {width:24px; height:24px; border-radius:50%; display:inline-flex;
  align-items:center; justify-content:center; font-weight:bold; font-size:14px;}
.ic.ok {background:#22c55e;} .ic.bad {background:#ef4444;}
.ic.wt {color:#888 !important; font-size:20px;}
.spin {width:22px; height:22px; border:4px solid #444; border-top-color:#ec4899;
  border-right-color:#3b82f6; border-radius:50%; animation:r .9s linear infinite;}
@keyframes r {to {transform:rotate(360deg);}}
"""

JS_LOAD_KEY = "() => { try { return localStorage.getItem('on3_key') || ''; } catch(e) { return ''; } }"
JS_SAVE_KEY = "(k) => { try { if (k) localStorage.setItem('on3_key', k); } catch(e) {} }"
JS_CLEAR_KEY = "() => { try { localStorage.removeItem('on3_key'); } catch(e) {} }"
JS_DOWNLOAD = """(f) => {
  if (!f) return;
  const u = f.url || f.path || f;
  const a = document.createElement('a');
  a.href = u; a.download = f.orig_name || 'voice.mp3';
  document.body.appendChild(a); a.click(); a.remove();
}"""

QUALITY = {"မြန်": 8, "ပုံမှန် (အကြံပြု)": 10, "ကောင်း (နှေးနိုင်)": 16}

# ---------- Reference ----------
def prepare_ref(file):
    if file is None: return None
    src = file if isinstance(file, str) else file.name
    out = f"work/ref_{uuid.uuid4().hex[:8]}.wav"
    base = ["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-t", "12"]
    try:
        subprocess.run(base + ["-af", "silenceremove=start_periods=1:start_threshold=-45dB,"
                               "highpass=f=80,loudnorm=I=-20:TP=-2", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        subprocess.run(base + [out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out

# ---------- Text ----------
MAX_CHUNK = 300

def clean_text(t):
    t = t.replace("\r", "")
    t = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", "", t)
    t = re.sub(r"[^\S\n]+", " ", t)
    return t.strip()

def cut_long(s, maxlen):
    out = []
    while len(s) > maxlen:
        win = s[:maxlen]
        k = max(win.rfind("၊"), win.rfind(" "), win.rfind(","))
        if k < maxlen // 2: k = maxlen - 1
        out.append(s[:k + 1].strip()); s = s[k + 1:].strip()
    if s: out.append(s)
    return out

def split_text(t, maxlen=MAX_CHUNK, minlen=25):
    t = clean_text(t)
    if len(t) <= maxlen: return [t]
    sents = [s.strip() for s in re.split(r"(?<=[။!?])\s*|\n+", t) if s and s.strip()]
    pieces = []
    for s in sents: pieces += cut_long(s, maxlen)
    chunks, cur = [], ""
    for s in pieces:
        if cur and len(cur) + 1 + len(s) > maxlen:
            chunks.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip() if cur else s
    if cur: chunks.append(cur)
    if len(chunks) > 1 and len(chunks[-1]) < minlen:
        chunks[-2] += " " + chunks.pop()
    return chunks

# ---------- Audio ----------
def call_gen(**kw):
    optional = ["retry_badcase", "retry_badcase_max_times", "normalize", "denoise"]
    while True:
        try:
            return model.generate(**kw)
        except TypeError as e:
            bad = next((k for k in optional if k in kw and k in str(e)), None)
            if not bad: raise
            kw.pop(bad)

def gen_chunk(text, ref, steps):
    w = None
    for _ in range(2):
        w = np.asarray(call_gen(text=text, reference_wav_path=ref, cfg_value=2.0,
                                inference_timesteps=steps, retry_badcase=True,
                                retry_badcase_max_times=2, normalize=False,
                                denoise=False), dtype=np.float32).squeeze()
        spc = len(w) / SR / max(len(text.replace(" ", "")), 1)
        if 0.04 <= spc <= 0.30: break
    return w

def tidy(w):
    w = w.astype(np.float32).copy()
    m = float(np.abs(w).max()) or 1.0
    idx = np.where(np.abs(w) > 0.02 * m)[0]
    if len(idx):
        pad = int(0.05 * SR)
        w = w[max(idx[0] - pad, 0): idx[-1] + pad]
    rms = float(np.sqrt(np.mean(w ** 2))) + 1e-8
    w = np.clip(w * min(0.1 / rms, 4.0), -1, 1)
    f = int(0.015 * SR)
    if len(w) > 2 * f:
        w[:f] *= np.linspace(0, 1, f, dtype=np.float32)
        w[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return w

def join_audio(parts):
    gap = np.zeros(int(SR * 0.20), dtype=np.float32)
    out = []
    for i, p in enumerate(parts):
        out.append(tidy(p))
        if i < len(parts) - 1: out.append(gap)
    y = np.concatenate(out)
    return (y / (float(np.abs(y).max()) or 1.0) * 0.95).astype(np.float32)

# ---------- Pages ----------
def show(n):
    return [gr.update(visible=(i == n)) for i in range(4)]

def login(key):
    ok, msg, _ = check_key(key)
    if not ok:
        gr.Warning(msg); return show(0) + ["", ""]
    gr.Info(msg)
    return show(1) + [key.strip(), f"<div class='badge'>🔑 Key မှန်ပါသည် — {msg}</div>"]

def login_auto(key):
    if not (key or "").strip():
        return show(0) + ["", ""]
    return login(key)

def logout():
    return show(0) + ["", "", ""]

def to2(ref):
    if not ref:
        gr.Warning("Video သို့မဟုတ် Audio အရင်ထည့်ပါ"); return show(1)
    return show(2)

def to3(text):
    if not text or not text.strip():
        gr.Warning("စာထည့်ပါ"); return show(2) + [IDLE, None, None, None]
    return show(3) + [render(["run", "wait", "wait", "wait"]), None, None, None]

def restart():
    return show(1) + [None, None, "", IDLE, None, None, None, ""]

def generate(key, ref_audio, text, quality):
    st = ["run", "wait", "wait", "wait"]
    yield render(st), None, None
    ok, msg, _ = check_key(key)
    if not ok or not ref_audio or not text or not text.strip():
        st[0] = "err"
        yield render(st, {0: msg if not ok else "အချက်အလက်မပြည့်စုံပါ"}), None, None; return
    st[0] = "done"; st[1] = "run"; yield render(st, {0: msg}), None, None
    chunks = split_text(text); n = len(chunks)
    st[1] = "done"; st[2] = "run"
    info = {0: msg, 1: f"{n} အပိုင်း", 2: f"0/{n}"}
    yield render(st, info), None, None
    try:
        steps = QUALITY.get(quality, 10)
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(gen_chunk(c, ref_audio, steps))
            info[2] = f"{i}/{n}"
            yield render(st, info), None, None
        p = f"work/out_{uuid.uuid4().hex[:8]}.wav"
        sf.write(p, join_audio(parts), SR)
        st[2] = "done"; st[3] = "done"
        yield render(st, info), p, p
    except Exception as e:
        st[2] = "err"; info[2] = f"အမှား: {e}"
        yield render(st, info), None, None

def make_mp3(wav_path, name):
    if not wav_path:
        gr.Warning("အသံမထွက်သေးပါ"); return None
    nm = "".join(c for c in (name or "").strip() if c not in '\\/:*?"<>|')
    nm = nm or f"voice_{uuid.uuid4().hex[:6]}"
    mp3 = f"work/{nm}.mp3"
    subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame",
                    "-q:a", "2", mp3], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return mp3

# ---------- UI ----------
with gr.Blocks(css=CSS, theme=gr.themes.Base()) as demo:
    gr.Markdown("# 🎙️ မြန်မာ Voice Clone (VoxCPM2)")
    key_info = gr.HTML("")
    wav_state, key_state = gr.State(), gr.State("")

    with gr.Column(visible=True) as p0:
        gr.Markdown("### 🔑 Key ထည့်ပါ")
        key_in = gr.Textbox(label="License Key (တစ်ခါထည့်ရင် မှတ်ထားမယ်)",
                            placeholder="VIP.1790000000.XXXXXXXX....")
        next0 = gr.Button("Next ▶", elem_classes="btn")

    with gr.Column(visible=False) as p1:
        gr.Markdown("### အဆင့် ၁ — Video သို့မဟုတ် Audio")
        gr.Markdown("💡 ဆူညံသံမရှိတဲ့ ၈–၁၂ စက္ကန့် အသံက အကောင်းဆုံးပါ")
        up = gr.File(label="Video / Audio ထည့်ပါ", file_types=["audio", "video"])
        ref_prev = gr.Audio(label="စမ်းနားထောင်ရန်", type="filepath", interactive=False)
        next1 = gr.Button("Next ▶", elem_classes="btn")
        logout_btn = gr.Button("🔑 Key ပြောင်းမည်", elem_classes="back")

    with gr.Column(visible=False) as p2:
        gr.Markdown("### အဆင့် ၂ — စာထည့်ပါ")
        text = gr.Textbox(label="ပြောစေချင်တဲ့ မြန်မာစာ", lines=7)
        clean_btn = gr.Button("🧹 Clean", elem_classes="back")
        quality = gr.Dropdown(list(QUALITY.keys()), value="ပုံမှန် (အကြံပြု)",
                              label="အရည်အသွေး (မြင့်ရင် ပိုကြာတယ်)")
        with gr.Row():
            back2 = gr.Button("◀ Back", elem_classes="back")
            next2 = gr.Button("Next ▶", elem_classes="btn")

    with gr.Column(visible=False) as p3:
        gr.Markdown("### အဆင့် ၃ — လုပ်ဆောင်ချက်")
        status = gr.HTML(IDLE)
        out_audio = gr.Audio(label="ထွက်လာတဲ့အသံ — နားထောင်ရန်", type="filepath",
                             interactive=False)
        fname = gr.Textbox(label="MP3 ဖိုင်အမည် (မပေးလည်းရ)", placeholder="my_voice")
        dl_btn = gr.Button("⬇ MP3 ဒေါင်းလုဒ်", elem_classes="btn")
        dl_file = gr.File(label="mp3", elem_classes="hide")
        again = gr.Button("🔄 အသစ်ပြန်စမည်", elem_classes="back")

    pages = [p0, p1, p2, p3]

    demo.load(None, None, key_in, js=JS_LOAD_KEY) \
        .then(login_auto, key_in, pages + [key_state, key_info])
    demo.load(track_visit, None, None)
    if hasattr(gr, "Timer"):
        timer = gr.Timer(30)
        timer.tick(heartbeat, key_state, None)

    next0.click(login, key_in, pages + [key_state, key_info]) \
         .then(None, key_state, None, js=JS_SAVE_KEY)
    logout_btn.click(logout, None, pages + [key_in, key_state, key_info]) \
              .then(None, None, None, js=JS_CLEAR_KEY)

    up.change(prepare_ref, up, ref_prev)
    next1.click(to2, ref_prev, pages)
    back2.click(lambda: show(1), None, pages)
    clean_btn.click(lambda: "", None, text)
    next2.click(to3, text, pages + [status, out_audio, wav_state, dl_file]) \
         .then(generate, [key_state, ref_prev, text, quality],
               [status, out_audio, wav_state])

    dl_btn.click(make_mp3, [wav_state, fname], dl_file) \
          .then(None, dl_file, None, js=JS_DOWNLOAD)

    again.click(restart, None, pages + [up, ref_prev, text, status,
                                        out_audio, wav_state, dl_file, fname])

demo.queue().launch(share=True, debug=True)
