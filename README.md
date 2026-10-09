# indic-synthetic-docs

Generate synthetic, degraded images of old Indic-language documents, with exact ground-truth text, for
testing OCR / text-extraction models. Currently: **Tamil sale deeds** (கிரைய ஆவணம்).

Each page's text is generated, so ground truth is exact and free. Clean and degraded versions share the
same text, so degradation is the only variable.

## Quick start

```bash
pip install -r requirements.txt
python generate.py --out out --n 10 --level all --seed 0
```

Requires Python 3.9+ and Chrome or Chromium (used to render Tamil with correct shaping). Pass `--chrome PATH`
or set `$CHROME` if it isn't auto-detected. The default font list is `Tamil Sangam MN` (macOS), `Noto Sans Tamil`,
`Latha`; use `--font` for another Tamil-capable font (on Linux: `apt install fonts-noto`).

Options: `--n` pages, `--level mild|moderate|severe|all`, `--seed` (page *i* uses `seed+i`; runs are reproducible).

## Output (per page)

| File | Contents |
|---|---|
| `deed_NNNNN_pressed.png` | clean letterpress-style render (no aging) |
| `deed_NNNNN_{mild,moderate,severe}.jpg` | aged and scanned versions |
| `deed_NNNNN.txt` | ground-truth text, in reading order |
| `deed_NNNNN.json` | the random fields used (names, place, date, price, survey number) |

See [`examples/`](examples/) for one page at every level.

## How it works

1. **Content.** Names, place, date, price, survey number and boundaries are sampled from small lists
   (all fictional) and slotted into a fixed deed template.
2. **Render.** HTML/CSS in headless Chrome. Each grapheme cluster gets a random offset, rotation, scale,
   spacing and ink density, which imitates uneven letterpress.
3. **Degrade.** A hand-built physical model, applied in the order damage happens:
   ink (ragged edges via noise + sigmoid, patchy fading, worn specks, bleed, show-through from the reverse),
   paper (low-saturation tone, fibres, binding shadow, tide-line stains, specks, scratches, fold),
   then scan (skew and page curl, uneven lighting, banding, sensor noise, blur, down/up-sampling, JPEG).

## Limitations

- **Not calibrated against real scans.** The parameters were tuned by eye. Model rankings on this data may not
  transfer to real documents; keep a small real, hand-transcribed hold-out set.
- **Modern script only.** Output uses modern Unicode Tamil, a modern system font and Arabic numerals. Real
  mid-20th-century documents used pre-reform letterforms, Tamil numerals, Grantha letters and period spelling.
- **Tamil text has not been proofread by a native speaker.** The wording is a plausible approximation, not
  authentic legal language. Treat names and amounts as fictional.
- Fixed layout (single page, one template). Dust, stains and signatures are more regular than real ones.

## License

MIT. See [LICENSE](LICENSE).
