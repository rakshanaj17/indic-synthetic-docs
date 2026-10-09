#!/usr/bin/env python3
"""Generate synthetic, degraded Tamil sale-deed page images with exact ground truth.

Stage 1: render a clean "letterpress" page with headless Chrome (correct Tamil shaping).
Stage 2: apply a physical aging + scanning model (ink, paper, dirt, scan geometry).
"""
import argparse, html, json, os, platform, random, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates

W, H = 1000, 1300

# ------------------------------------------------------------------ content
NAMES = ["சுப்பிரமணியம்", "வெங்கடேசன்", "இராமசாமி", "கோவிந்தராஜன்", "முருகன்", "கண்ணன்",
         "ஆறுமுகம்", "பழனியப்பன்", "செல்வராஜ்", "மாணிக்கம்", "நடராஜன்", "துரைசாமி",
         "இராமலிங்கம்", "சின்னசாமி", "அண்ணாமலை", "கணேசன்"]
PLACES = [("சென்னை", "மயிலாப்பூர்"), ("சென்னை", "சைதாப்பேட்டை"), ("தஞ்சாவூர்", "கும்பகோணம்"),
          ("மதுரை", "திருமங்கலம்"), ("சேலம்", "ஆத்தூர்"), ("திருச்சிராப்பள்ளி", "லால்குடி")]
MONTHS = ["சனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "சூன்",
          "சூலை", "ஆகத்து", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "திசம்பர்"]
HOUSES = ["ஓட்டு வீடு", "காரை வீடு", "கூரை வீடு"]
ROADS = ["சாலை", "பொது வீதி", "ஏரி வாய்க்கால்", "கோயில் நிலம்"]


def make_content(rng):
    seller, seller_f, buyer, buyer_f, n1, n2, w1, w2 = rng.sample(NAMES, 8)
    district, village = rng.choice(PLACES)
    year, month, day = rng.randint(1950, 1975), rng.choice(MONTHS), rng.randint(1, 28)
    price = rng.randrange(3000, 60000, 500)
    ew, ns = rng.randrange(20, 60, 5), rng.randrange(30, 90, 5)
    survey = f"{rng.randint(10, 480)}/{rng.randint(1, 9)}"
    house = rng.choice(HOUSES)
    r1, r2 = rng.sample(ROADS, 2)
    lines = [
        ("title", "கிரைய ஆவணம்"),
        ("body", f"இந்தக் கிரைய ஆவணம் {year} ஆம் ஆண்டு {month} மாதம் {day} ஆம் தேதி {district} மாவட்டம், "
                 f"{village} கிராமத்தில் வசித்துவரும் {seller_f} மகன் {seller} (இனி “விற்பவர்” என்று குறிப்பிடப்படுவார்) "
                 f"என்பவரால், அதே ஊரில் வசித்துவரும் {buyer_f} மகன் {buyer} (இனி “வாங்குபவர்” என்று "
                 f"குறிப்பிடப்படுவார்) என்பவருக்கு எழுதிக் கொடுக்கப்பட்டது."),
        ("body", f"நான் இதுவரை அனுபவித்து வந்த கீழ்க்காணும் சொத்தை உமக்கு ரூ. {price:,} விலைக்குக் கிரயம் "
                 f"செய்து கொடுத்துள்ளேன். அத்தொகை முழுவதையும் இன்று உம்மிடமிருந்து ரொக்கமாகப் பெற்றுக்கொண்டேன்."),
        ("body", "1. மேற்படி சொத்தில் எனக்குள்ள உரிமை முழுவதையும் இன்று முதல் நீர் அனுபவித்துக் கொள்ளலாம்."),
        ("body", "2. இச்சொத்து வேறு எவருக்கும் அடமானமாகவோ விற்பனையாகவோ கொடுக்கப்படவில்லை என்று உறுதி கூறுகிறேன்."),
        ("body", "3. இச்சொத்தின் மீது வில்லங்கம் ஏதேனும் இருப்பின் அதை நானே நீக்கிக் கொடுப்பேன்."),
        ("head", "சொத்து விவரம்"),
        ("body", f"{district} மாவட்டம், {village} கிராமம், புல எண் {survey} இல் அடங்கிய, கிழக்கு மேற்கு {ew} அடியும் "
                 f"தெற்கு வடக்கு {ns} அடியும் ஆக {ew * ns} சதுர அடி கொண்ட காலி மனையும் அதிலுள்ள {house}ம்."),
        ("body", f"எல்லைகள்: கிழக்கில் {r1}; மேற்கில் {n1} வீடு; தெற்கில் {r2}; வடக்கில் {n2} மனை."),
        ("body", f"இதற்குச் சாட்சிகள்: 1. {w1}  2. {w2}"),
    ]
    return lines, dict(seller=seller, buyer=buyer, district=district, village=village, year=year,
                       month=month, day=day, price=price, survey=survey, area_sqft=ew * ns)


# ------------------------------------------------------------------ stage 1: render
def sig(d):
    return (f'<svg class="sig" viewBox="0 0 220 70"><path d="{d}" fill="none" stroke="#111" '
            f'stroke-width="2.6" stroke-linecap="round"/></svg>')


def build_html(lines, font, jitter_seed):
    body = "\n".join(f'<p class="t {c}">{html.escape(t)}</p>' for c, t in lines)
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#fff;width:{W}px;height:{H}px;font-family:{font};color:#111;position:relative}}
.frame{{position:absolute;inset:34px;border:3px double #111}}
.stamp{{position:absolute;top:62px;right:70px;border:2px solid #111;padding:6px 18px;text-align:center;font-size:22px}}
.stamp b{{font-size:30px}}
.wrap{{position:absolute;left:96px;right:96px;top:160px}}
p{{margin:0 0 14px;font-size:22px;line-height:1.65}}
.title{{text-align:center;font-size:38px;font-weight:bold;margin-bottom:22px;text-decoration:underline}}
.head{{text-align:center;font-weight:bold;font-size:24px;margin-top:18px}}
span.g{{display:inline-block;white-space:pre}}
.sigrow{{position:absolute;left:96px;right:96px;top:1120px;display:flex;justify-content:space-between;font-size:22px;text-align:center}}
.sig{{width:200px;height:64px;display:block;margin:0 auto 2px}}
.seal{{position:absolute;left:760px;top:990px;width:125px;height:125px;opacity:.9}}
</style>
<div class="frame"></div><div class="stamp t"><b>ரூ. 100</b></div>
<div class="wrap">{body}</div>
<svg class="seal" viewBox="0 0 150 150"><circle cx="75" cy="75" r="68" fill="none" stroke="#111" stroke-width="3"/><circle cx="75" cy="75" r="54" fill="none" stroke="#111" stroke-width="1.5"/><path d="M75 38 L83 62 L108 62 L88 77 L96 102 L75 87 L54 102 L62 77 L42 62 L67 62Z" fill="#111"/></svg>
<div class="sigrow">
 <div>{sig("M10 45 C30 5 40 60 60 25 S90 55 110 20 S150 50 175 30 L210 36")}<span class="t">விற்பவர் கையொப்பம்</span></div>
 <div>{sig("M15 40 C35 10 45 55 70 30 S110 52 140 28 L200 42")}<span class="t">சாட்சி</span></div>
 <div>{sig("M20 30 C40 60 55 5 80 38 S120 20 150 45 L190 22")}<span class="t">சாட்சி</span></div>
</div>
<script>
let seed={jitter_seed};const r=()=>{{seed=(seed*16807)%2147483647;return seed/2147483647}};
const seg=new Intl.Segmenter('ta',{{granularity:'grapheme'}});
document.querySelectorAll('.t').forEach(el=>{{
  const t=el.textContent;el.textContent='';const words=t.split(' ');
  words.forEach((word,wi)=>{{
   const w=document.createElement('span');w.style.whiteSpace='nowrap';w.style.display='inline-block';
   for(const {{segment}} of seg.segment(word)){{
    const sp=document.createElement('span');sp.className='g';sp.textContent=segment;
    const dy=(r()-.5)*3,rot=(r()-.5)*2.2,sx=.96+r()*.08,sy=.96+r()*.08;
    sp.style.transform=`translateY(${{dy}}px) rotate(${{rot}}deg) scale(${{sx}},${{sy}})`;
    sp.style.opacity=.72+r()*.28;sp.style.letterSpacing=((r()-.5)*1.4)+'px';
    sp.style.textShadow=`0 0 ${{.4+r()*1.2}}px rgba(0,0,0,.55)`;
    w.appendChild(sp);
   }}
   el.appendChild(w);if(wi<words.length-1)el.appendChild(document.createTextNode(' '));
  }});
}});
</script>"""


def find_chrome(explicit=None):
    cands = [explicit, os.environ.get("CHROME"),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
             shutil.which("chrome")]
    for c in cands:
        if c and os.path.exists(c):
            return c
    sys.exit("Chrome/Chromium not found. Install it or pass --chrome / set $CHROME.")


def render(html_text, out_png, chrome):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "page.html")
        open(p, "w", encoding="utf-8").write(html_text)
        subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={W},{H}", f"--screenshot={out_png}", f"file://{p}"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ stage 2: degrade
# gain, fade_floor, ink_loss, bleed, blur, scale, jpeg_q, sensor_noise, dirt, wash, edge_noise
LEVELS = {
    "mild":     (1.15, 0.45, 0.05, 0.5, 0.45, 0.95, 70, 0.020, 0.8, 0.03, 0.06),
    "moderate": (1.00, 0.25, 0.20, 0.8, 0.70, 0.80, 55, 0.030, 1.4, 0.10, 0.10),
    "severe":   (0.85, 0.05, 0.40, 1.1, 0.95, 0.65, 40, 0.045, 2.2, 0.20, 0.14),
}


def degrade(pressed_png, level, seed):
    gain, floor, loss, bleed, blur, scale, q, nz, dirt, wash, ea = LEVELS[level]
    rng = np.random.default_rng(seed)
    img = np.asarray(Image.open(pressed_png).convert("L")).astype(np.float32) / 255
    h, w = img.shape
    yy, xx = np.mgrid[0:h, 0:w]

    def noise(sigma):
        n = gaussian_filter(rng.standard_normal((h, w)), sigma); n -= n.min(); return n / n.max()

    # ink: ragged edges, patchy fading, worn specks; old ink is never true black
    ink = gaussian_filter(1 - img, 0.9)
    en = gaussian_filter(rng.standard_normal((h, w)), 1.3); en /= en.std()
    ink = 1 / (1 + np.exp(-(ink - 0.42 + ea * en) * 14))
    ink = np.clip(gaussian_filter(ink, bleed) * gain, 0, 1)
    ink *= np.clip(floor + 1.2 * noise(30), 0, 1)
    ink *= (rng.random((h, w)) > loss * noise(2)).astype(np.float32)
    ink *= 0.88
    back = gaussian_filter(ink[:, ::-1], 3.0) * 0.22          # show-through from reverse side

    # paper: light, low-saturation, fibrous, with binding shadow, stains, dirt, crease
    paper = np.ones((h, w, 3), np.float32) * np.array([0.90, 0.86, 0.77], np.float32)
    tone = noise(60) * 0.10 + noise(18) * 0.05 + gaussian_filter(rng.standard_normal((h, w)), (0.6, 2.5)) * 0.035 \
        + rng.standard_normal((h, w)) * 0.012
    bind = np.exp(-(xx / 70.0)) * 0.22 + np.exp(-((w - xx) / 40.0)) * 0.10
    edges = (np.exp(-yy / 30.0) + np.exp(-(h - yy) / 30.0)) * 0.08
    stain = np.zeros((h, w), np.float32)
    for _ in range(1 if level == "mild" else 2):
        cx, cy, r = rng.integers(150, w - 150), rng.integers(300, h - 150), rng.integers(90, 190)
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) + 750 * gaussian_filter(rng.standard_normal((h, w)), 30)
        stain += np.exp(-((d - r) / 14) ** 2) * 0.07 + (d < r) * 0.03
    paper -= (tone + bind + edges + stain)[..., None] * np.array([0.7, 0.9, 1.2], np.float32)
    speck = gaussian_filter((rng.random((h, w)) > 0.9994).astype(np.float32), 1.0) * dirt * 6
    paper -= speck[..., None] * 0.55
    scr = np.zeros((h, w), np.float32)
    for _ in range(int(6 * dirt)):
        x0, y0, ang, n = rng.integers(0, w), rng.integers(0, h), rng.uniform(0, np.pi), rng.integers(60, 260)
        for t in range(n):
            x, y = int(x0 + t * np.cos(ang) + 8 * np.sin(t / 17)), int(y0 + t * np.sin(ang))
            if 0 <= x < w and 0 <= y < h:
                scr[y, x] = 1
    paper -= (gaussian_filter(scr, 0.7) * 0.35)[..., None]
    sm = gaussian_filter((rng.random((h, w)) > 0.99999).astype(np.float32), 40)
    paper -= (sm / (sm.max() + 1e-9) * 0.10 * dirt)[..., None]
    paper -= (np.exp(-((yy - 650) / 2.5) ** 2) * 0.10 + np.exp(-((yy - 657) / 9.0) ** 2) * 0.04)[..., None]

    out = paper * (1 - (ink + back)[..., None] * 0.95)
    out = out * (1 - wash) + wash * out.mean()

    # scan geometry + sensor
    ang = np.deg2rad(0.8 if level == "mild" else 1.4)
    xs = xx + (yy - h / 2) * np.sin(ang) + 5 * np.sin(yy / h * np.pi)
    ys = yy - (xx - w / 2) * np.sin(ang)
    out = np.stack([map_coordinates(out[..., c], [ys, xs], order=1, mode="constant", cval=0.18) for c in range(3)], -1)
    out *= 1 - 0.06 * (xx / w)[..., None] - 0.04 * noise(120)[..., None]
    out *= 1 + gaussian_filter1d(rng.standard_normal(h), 1.5)[:, None, None] * 0.01
    out += rng.normal(0, nz, out.shape)
    im = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    im = im.resize((int(w * scale), int(h * scale)), Image.BILINEAR).resize((w, h), Image.BICUBIC)
    return im, q


# ------------------------------------------------------------------ cli
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="out", help="output directory")
    ap.add_argument("--n", type=int, default=3, help="number of pages")
    ap.add_argument("--level", default="all", choices=[*LEVELS, "all"], help="degradation level")
    ap.add_argument("--seed", type=int, default=0, help="base seed; page i uses seed+i")
    ap.add_argument("--font", default='"Tamil Sangam MN","Noto Sans Tamil","Latha","Tamil MN",sans-serif',
                    help="CSS font-family; must contain Tamil glyphs")
    ap.add_argument("--chrome", help="path to Chrome/Chromium (or set $CHROME)")
    a = ap.parse_args()

    chrome = find_chrome(a.chrome)
    os.makedirs(a.out, exist_ok=True)
    levels = list(LEVELS) if a.level == "all" else [a.level]
    for i in range(a.n):
        seed, pid = a.seed + i, f"deed_{a.seed + i:05d}"
        lines, meta = make_content(random.Random(seed))
        pressed = os.path.join(a.out, f"{pid}_pressed.png")
        render(build_html(lines, a.font, seed * 7919 % 2147483646 + 1), pressed, chrome)
        gt = [lines[0][1], "ரூ. 100"] + [t for _, t in lines[1:]] + ["விற்பவர் கையொப்பம்", "சாட்சி", "சாட்சி"]
        open(os.path.join(a.out, f"{pid}.txt"), "w", encoding="utf-8").write("\n".join(gt) + "\n")
        json.dump({"id": pid, "seed": seed, "levels": levels, **meta},
                  open(os.path.join(a.out, f"{pid}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        for lv in levels:
            im, q = degrade(pressed, lv, seed)
            im.save(os.path.join(a.out, f"{pid}_{lv}.jpg"), quality=q)
        print(f"wrote {pid} ({', '.join(levels)})")


if __name__ == "__main__":
    main()
