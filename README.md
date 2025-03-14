# image toolkit

An interactive terminal tool for four jobs:

- **HEIC / HEIF → JPG or PNG** — iPhone photos into something everything can open
- **JPG / PNG → WebP** — lossy or lossless, transparency preserved
- **Resize JPG / PNG** — scale down to fit a box or a percentage
- **Compress JPG / PNG** — shrink a file by a target percentage

No GUI, no flags to memorise. Run it, answer the prompts with the arrow keys.

## Install

```bash
cd tools/image_toolkit
./setup.sh
```

This creates a self-contained `.venv/` here. Nothing is installed system-wide,
no Homebrew packages are needed.

## Run

```bash
./imgkit
```

Optionally put it on your PATH:

```bash
ln -s "$PWD/imgkit" /usr/local/bin/imgkit
```

## How the compressor works

You give it a percentage — "make these 60% smaller" — not a quality number.

For **JPEG** it binary-searches the encoder quality scale (95 down to 20) and
keeps the *highest* quality whose output still fits under your target. That is
about seven encodes instead of seventy-five.

For **PNG**, which is lossless and has no quality dial, the only lever is
colour count. It tries full colour first, then palettes of 256, 128, 64, 32,
16 and 8 colours, and stops at the first one that fits.

If your target simply cannot be reached — asking an already-squeezed thumbnail
to lose another 95% — it still writes the best result it managed, but reports
the file as **short of target** and tells you what it actually achieved. It
will not claim it hit a number it missed. Output is never larger than the
input; if re-encoding would inflate a file, the original bytes are copied
instead.

## The menu

Operations are cards in a grid, two per row, each in its own colour:

```
┏━ 1 ━━━━━━━━━━━━━━━━━━━━┓   ╭─ 2 ────────────────────╮
┃ HEIC / HEIF            ┃   │ JPG / PNG              │
┃ → JPG or PNG           ┃   │ → WebP                 │
┗━━━━━━━━━━━━━━━━━━━━━━━━┛   ╰────────────────────────╯

╭─ 3 ────────────────────╮   ╭─ 4 ────────────────────╮
│ Compress               │   │ Quit                   │
│ shrink to a target size│   │ leave the toolkit      │
╰────────────────────────╯   ╰────────────────────────╯
```

Arrow keys move, `1`-`4` jump straight to a card and run it, enter selects,
escape quits. The selected card is drawn with a heavy border as well as a
brighter colour, so the selection is still visible over SSH, in a pipe, or in
any terminal without truecolour. Below about 55 columns the grid drops to a
single column.

## Your photos know where you live

Phones write GPS coordinates into every picture. Converting a photo and posting
it can publish the place it was taken, which for a photo shot at home is your
home address.

Every operation asks what to do with that record:

| Choice | Camera, lens, date | Location |
|---|---|---|
| Keep camera and date, drop location *(default)* | kept | **removed** |
| Strip everything | removed | **removed** |
| Keep everything | kept | kept |

The default drops location, because publishing it should take a deliberate
choice rather than an oversight. The orientation tag is always removed, in
every mode — the rotation has already been applied to the pixels, so leaving
the tag would rotate the image a second time.

## Resize

Pick a preset box (1920, 1200 or 800), a percentage, or your own maximum width
and height. The aspect ratio is always preserved and the image is **never
enlarged** — asking for 200% of an 800px photo gives you the 800px photo back,
because enlarging only invents detail that was never captured.

Quality is fixed at 92, deliberately high: downscaling has already discarded
detail and there is no sense throwing away more in the same pass. Run the
compressor afterwards when you want to trade quality for size on purpose.

Before you confirm, the preview measures one real file at your chosen
dimensions and shows the estimated total.

## Bulk

Point it at a folder instead of a file and it works on everything inside:

- The extension filter follows the operation — HEIC mode only picks up
  `.heic` and `.heif`, WebP and compress modes only `.jpg`, `.jpeg` and `.png`.
- Answer yes to "include subfolders?" and it walks the whole tree.
- One progress bar, one summary, one total.
- A corrupt file is logged as failed and the batch keeps going.
- The output folder is excluded from the scan, so a re-run does not eat its
  own results.

A recursive run flattens the tree into one output folder, so two files with
the same name in different subfolders would want the same output. The first
one claims the name and later ones are numbered:

```
src/a/photo.jpg  ->  out/photo.webp
src/b/photo.jpg  ->  out/photo-2.webp
```

The preview lists every rename before you confirm. Comparison is
case-insensitive, because macOS treats `Photo.webp` and `photo.webp` as one
file. A source genuinely named `photo-2.jpg` claims `photo-2.webp` for itself
and the collision skips past to `photo-3.webp`.

Two things bulk does not do: it runs sequentially, so two hundred photos take
two hundred times one photo; and there is no filename pattern filter, so it is
every matching image in the folder or none.

## It tells you the size before you commit

Pick a source and you get a box describing it — name, size, dimensions,
format, location; or for a folder, how many matching images sit at the top
level and how many are nested below, which is the information you need to
answer the "include subfolders?" question sensibly.

Then, as you type a quality or a percentage, the estimated output size appears
beside the prompt and updates on every keystroke:

```
? JPEG quality (1-100): 90        ≈ 2.4 MB  (from 1.8 MB, +44%)
? Shrink files by what percent? (1-99): 60        ≈ 735 KB  (from 1.8 MB, -60%)
```

For the compressor this is exact — the target *is* the arithmetic.

For a quality setting there is no formula, because output size depends on the
picture. So one real file is encoded at eight quality anchors when you reach
the prompt (about 1.3 seconds for a 12MP photo, shown with a spinner) and
everything between them is interpolated. Measured against the actual encoder
on a 12MP iPhone photo, that lands within about 4% across most of the scale
and exactly on the default of 90. It drifts to roughly 11% at quality 97,
where the curve is steepest — hence the `≈`.

For a folder, the median-sized file is the one sampled and the result is
scaled to the batch, which the prompt says out loud. Median rather than first
or largest, so one panorama among a hundred snapshots does not set the
expectation for all of them.

## HEIC → JPG usually makes the file *bigger*

This is not a bug. HEIC compresses far better than JPEG, so a 1.8 MB iPhone
HEIC re-encoded at JPEG quality 90 lands around 2.4 MB. You are trading size
for compatibility. The summary says **Size increase** rather than pretending
it saved you anything.

If you want compatibility *and* a smaller file, convert to WebP instead, or
run the compressor over the JPEGs afterwards. Dropping the JPEG quality to
around 75 also brings it back under the original.

## Paths you can paste

The path prompts accept whatever your terminal gives you: tab completion's
trailing space, a quoted path, or a file dragged into the window with its
spaces backslash-escaped. All three are cleaned up before use.

## Things it will not do to your files

- **Originals are never modified.** Output always goes to a separate folder,
  `converted/` beside the source by default.
- **Existing output is not overwritten** unless you say yes at the prompt.
- **Compressing a file over itself is refused outright**, even if you point the
  output at the source folder.
- **A corrupt file does not kill the run.** It is recorded as failed and the
  batch carries on.

## A note on rotation

iPhone HEIC files are stored unrotated, with the rotation recorded in an EXIF
tag. Anything that reads the pixels without honouring that tag shows the photo
sideways. Every operation here bakes the rotation into the pixels and clears
the now-misleading tag, so a 1200×900 landscape-stored portrait comes out as a
genuine 900×1200 file.

## Layout

```
imgkit              launcher
setup.sh            creates .venv, installs dependencies
image_toolkit/
  core.py           the image operations — pure functions over paths
  discovery.py      finding the files to work on
  jobs.py           running one operation across many files
  planning.py       turning choices into a bound operation
  tui.py            the prompts and the rendering
tests/
```

`core`, `discovery`, `jobs` and `planning` know nothing about the TUI, so a
flag-driven CLI could be added on top without touching them.

## Tests

```bash
.venv/bin/python -m pytest
```

The tests generate real JPEG, PNG and HEIC files and run the real encoders —
nothing about the image pipeline is mocked.
