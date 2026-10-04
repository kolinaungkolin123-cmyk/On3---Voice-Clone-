import sys, subprocess
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "voxcpm", "gradio", "soundfile", "numpy", "pynacl"])

import os, re, uuid, base64, datetime, urllib.request
import numpy as np
import gradio as gr
import soundfile as sf
from nacl.signing import VerifyKey
from voxcpm import VoxCPM

# ====== ဒီနှစ်ကြောင်းကို ပြင်ပါ ======
PUBLIC_KEY = "IhTp+Sk042q9A1Oa04ifQFEWbUcBKv1AE2ZkwBKCawg="
REVOKED_URL = "https://raw.githubusercontent.com/kolinaungkolin123-cmyk/On3---Voice-Clone-/main/revoked.txt"
# =====================================

def check_key(key):
    try:
        pre, exp, rid, sig = (key or "").strip().split(".")
        if pre != "VIP": raise ValueError
        sig = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        VerifyKey(base64.b64decode(PUBLIC_KEY)).verify(f"{pre}.{exp}.{rid}".encode(), sig)
        end = datetime.datetime.strptime(exp, "%Y%m%d").date()
    except Exception:
        return False, "Key မှားနေပါသည်"
    try:
        bad = urllib.request.urlopen(REVOKED_URL, timeout=10).read().decode().split()
        if rid in bad: return False, "Key ကို ပိတ်ထားပါသည်"
    except Exception:
        pass
    today = datetime.datetime.now(datetime.timezone.utc).date()
    left = (end - today).days
    if left < 0: return False, "Key သက်တမ်းကုန်သွားပါပြီ"
    return True, f"Key မှန်ပါသည် — ကျန်ရက် {left} ရက်"

print("⏳ VoxCPM2 Model ဆွဲတင်နေပါသည်...")
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
:root, .gradio-container {
  --body-background-fill:#fff; --background-fill-primary:#fff;
  --background-fill-secondary:#fff; --block-background-fill:#fff;
  --body-text-color:#000; --block-label-text-color:#000;
  --block-title-text-color:#000; --input-background-fill:#fff;
  --border-color-primary:#ddd; --color-accent:#ec4899;
}
body, .gradio-container {background:#fff !important;}
*, label span, .prose, .prose *, h1, h2, h3, p, textarea, input {color:#000 !important;}
.block, .form, .panel {background:#fff !important;}
button.btn {background:linear-gradient(90deg,#ec4899,#3b82f6) !important;
  border:none !important; font-weight:700; font-size:18px !important;}
button.btn, button.btn * {color:#fff !important;}
button.back {background:#f3f4f6 !important; border:1px solid #ccc !important;}
.steps {border:2px solid #ec4899; border-radius:12px; padding:14px; background:#fff;}
.row {display:flex; align-items:center; gap:12px; font-size:17px; padding:6px 0;}
.ic {width:24px; height:24px; border-radius:50%; display:inline-flex;
  align-items:center; justify-content:center; font-weight:bold; font-size:14px;}
.ic.ok {background:#22c55e;} .ic.bad {background:#ef4444;}
.ic.ok, .ic.bad {color:#fff !important;}
.ic.wt {color:#999 !important; font-size:20px;}
.spin {width:22px; height:22px; border:4px solid #ddd; border-top-color:#ec4899;
  border-right-color:#3b82f6; border-radius:50%; animation:r .9s linear infinite;}
@keyframes r {to {transform:rotate(360deg);}}
"""

# ---------- JS ----------
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

def prepare_ref(file):
    if file is None: return None
    src = file if isinstance(file, str) else file.name
    out = f"work/ref_{uuid.uuid4().hex[:8]}.wav"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                    "-t", "30", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out

def split_text(t, maxlen=100):
    parts = [p.strip() for p in re.split(r"(?<=[။!?\n])", t) if p.strip()]
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) <= maxlen: cur += p
        else:
            if cur: chunks.append(cur)
            while len(p) > maxlen:
                chunks.append(p[:maxlen]); p = p[maxlen:]
            cur = p
    if cur: chunks.append(cur)
    return chunks

def show(n):
    return [gr.update(visible=(i == n)) for i in range(4)]

def to1(key):
    ok, msg = check_key(key)
    if not ok:
        gr.Warning(msg); return show(0) + [""]
    gr.Info(msg)
    return show(1) + [key.strip()]

def auto_login(key):                       # သိမ်းထားတဲ့ Key နဲ့ အလိုအလျောက်ဝင်
    key = (key or "").strip()
    if not key:
        return show(0) + [""]
    ok, msg = check_key(key)
    if not ok:
        gr.Warning(msg); return show(0) + [""]
    gr.Info(msg)
    return show(1) + [key]

def logout():
    return show(0) + ["", ""]

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

def generate(key, ref_audio, text):
    st = ["run", "wait", "wait", "wait"]
    yield render(st), None, None
    ok, msg = check_key(key)
    if not ok or not ref_audio or not text or not text.strip():
        st[0] = "err"
        yield render(st, {0: msg if not ok else "အချက်အလက်မပြည့်စုံပါ"}), None, None; return
    st[0] = "done"; st[1] = "run"; yield render(st, {0: msg}), None, None
    chunks = split_text(text.strip()); n = len(chunks)
    st[1] = "done"; st[2] = "run"
    info = {0: msg, 1: f"{n} အပိုင်း", 2: f"0/{n}"}
    yield render(st, info), None, None
    try:
        gap = np.zeros(int(SR * 0.25), dtype=np.float32); wavs = []
        for i, c in enumerate(chunks, 1):
            w = model.generate(text=c, reference_wav_path=ref_audio,
                               cfg_value=2.0, inference_timesteps=10)
            wavs += [np.asarray(w, dtype=np.float32), gap]
            info[2] = f"{i}/{n}"
            yield render(st, info), None, None
        p = f"work/out_{uuid.uuid4().hex[:8]}.wav"
        sf.write(p, np.concatenate(wavs), SR)
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

with gr.Blocks(css=CSS, theme=gr.themes.Base()) as demo:
    gr.Markdown("# 🎙️ မြန်မာ Voice Clone (VoxCPM2)")
    wav_state, key_state = gr.State(), gr.State("")

    with gr.Column(visible=True) as p0:
        gr.Markdown("### 🔑 Key ထည့်ပါ")
        key_in = gr.Textbox(label="License Key (တစ်ခါထည့်ရင် မှတ်ထားမယ်)",
                            placeholder="VIP.20261019.XXXXXXXX....")
        next0 = gr.Button("Next ▶", elem_classes="btn")

    with gr.Column(visible=False) as p1:
        gr.Markdown("### အဆင့် ၁ — Video သို့မဟုတ် Audio")
        up = gr.File(label="Video / Audio ထည့်ပါ", file_types=["audio", "video"])
        ref_prev = gr.Audio(label="စမ်းနားထောင်ရန်", type="filepath", interactive=False)
        next1 = gr.Button("Next ▶", elem_classes="btn")
        logout_btn = gr.Button("🔑 Key ပြောင်းမည်", elem_classes="back")

    with gr.Column(visible=False) as p2:
        gr.Markdown("### အဆင့် ၂ — စာထည့်ပါ")
        text = gr.Textbox(label="ပြောစေချင်တဲ့ မြန်မာစာ", lines=7)
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
        dl_file = gr.File(label="MP3 ဖိုင် (မဒေါင်းရင် ဒီကနေ နှိပ်ပါ)")
        again = gr.Button("🔄 အသစ်ပြန်စမည်", elem_classes="back")

    pages = [p0, p1, p2, p3]

    # Key မှတ်ထားခြင်း
    demo.load(None, None, key_in, js=JS_LOAD_KEY) \
        .then(auto_login, key_in, pages + [key_state])
    next0.click(to1, key_in, pages + [key_state]) \
         .then(None, key_state, None, js=JS_SAVE_KEY)
    logout_btn.click(logout, None, pages + [key_in, key_state]) \
              .then(None, None, None, js=JS_CLEAR_KEY)

    up.change(prepare_ref, up, ref_prev)
    next1.click(to2, ref_prev, pages)
    back2.click(lambda: show(1), None, pages)
    next2.click(to3, text, pages + [status, out_audio, wav_state, dl_file]) \
         .then(generate, [key_state, ref_prev, text], [status, out_audio, wav_state])

    # နှိပ်တာနဲ့ တိုက်ရိုက်ဒေါင်း
    dl_btn.click(make_mp3, [wav_state, fname], dl_file) \
          .then(None, dl_file, None, js=JS_DOWNLOAD)

    again.click(restart, None, pages + [up, ref_prev, text, status, out_audio,
                                        wav_state, dl_file, fname])

demo.queue().launch(share=True, debug=True)
