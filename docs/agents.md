# vidkit for AI agents

vidkit converts, compresses, trims, mutes and downloads video on the user's
own machine, using ffmpeg and yt-dlp. People use its menu. Agents and scripts
use its command line, which this guide covers: one command, every answer given
as an argument, a JSON report back.

```
vidkit mute ~/Movies/clips --recursive --json
```

## Before you start

```
command -v vidkit      # installed and on PATH?
vidkit --help          # the commands
vidkit mute --help     # one command's options
```

If `vidkit` is missing, the toolkit's `setup.sh` installs it and links it into
`~/.local/bin`. Everything except downloading needs ffmpeg
(`brew install ffmpeg`); without it those commands fail with exit code 1 and
say so.

**Never run `vidkit` with no arguments.** That is the interactive menu. With no
terminal attached it prints the help and exits with 2 rather than hanging, but
it does no work.

## The contract

These hold for every command.

- **Pass `--json`.** stdout is then exactly one JSON object. Notes about what
  is starting, and usage errors, go to stderr. `--json` can go before or after
  the command name.
- **Exit codes.**

  | Code | Meaning |
  |---|---|
  | 0 | It worked. Skipped files count as worked: there was nothing to do. |
  | 1 | Something failed. The report says what, per file. |
  | 2 | The command was wrong (bad option, missing file). Nothing was done. Read stderr. |

- **Sources are never modified or written over.** Output is a new file.
- **Default output folder** is `converted/` beside the source file, or
  inside the folder when given a folder. Every command shares it, so muting
  and compressing the same clip both land there, told apart by name.
  `--out DIR` chooses another. Downloads default to the current directory.
- **An existing output is skipped, not replaced.** Re-running a command is
  safe and does nothing twice. For a single file, `--overwrite` replaces an
  earlier output; folder runs always skip.
- **Paths in reports are absolute.**
- **Nothing is asked and nothing is remembered.** The same command always does
  the same thing.

## Commands

### `vidkit info FILE`

Reads a local video. Use it to check before acting, for example whether a
video has sound at all. Fast; writes nothing.

```
vidkit info clip.mov --json
```

```json
{
  "command": "info", "ok": true,
  "path": "/Users/me/clip.mov", "size_bytes": 20591580, "duration": 20.0,
  "width": 1920, "height": 1080, "video_codec": "h264", "audio_codec": "aac",
  "audio_bitrate": 152391, "video_bitrate": 8074903
}
```

`audio_codec` is `null` when there is no sound. Any field can be `null` when
the file does not record it.

### `vidkit convert PATH --to FORMAT`

Changes the container: `mp4`, `mkv`, `mov` or `webm`. When the streams are
already legal in the target it copies them, which is instant and lossless;
otherwise it re-encodes only what has to be. `clip.mkv` becomes `clip.mp4`.

| Option | |
|---|---|
| `--to FORMAT` | Required. `mp4`, `mkv`, `mov`, `webm`. |
| `--keep-codec` | AV1 or VP9 video can be copied into mp4/mov but QuickTime and Photos will not open it, so by default it is re-encoded to H.264. This copies it anyway. |
| `-r`, `--recursive` | Given a folder, include subfolders. |
| `--out DIR`, `--overwrite` | As above. |

PATH may be a folder: every video in it is converted. Files already in the
target format are skipped.

### `vidkit compress FILE --size SIZE`

Re-encodes one video to land near a target size: `25MB`, `800KB`, `1.5GB`, or
a bare number of megabytes. Slow: a full re-encode. Output keeps the source's
name, in the output folder, so `converted/clip.mp4` is the compressed one.

Sizes are binary: `MB` means 1024 × 1024 bytes. Most upload and email limits
are decimal, so a "5 MB" limit is 5,000,000 bytes, about `4.7MB` here. For a
hard limit, ask for about 10% under it.

One pass lands near the target, not exactly on it. A result over the target
has status `over` (exit code 0): the file exists but is too big. Try again with
a smaller `--size` and `--overwrite`. A target too small for the clip's length
fails before encoding anything.

### `vidkit trim FILE [--start T] [--end T] [--exact]`

Keeps only part of a video. Times are `90`, `1:30` or `1:02:03`; `--start`
defaults to the beginning and `--end` to the end. `clip.mp4` becomes
`clip-clip.mp4`.

By default the cut is instant and lossless but must start on a keyframe, so it
can come out longer than asked. When it does, `detail` gives the length
actually produced. `--exact` re-encodes for a frame-accurate cut, which is
slow.

### `vidkit mute PATH`

Removes the sound and copies the picture across untouched. Instant and
lossless. `clip.mov` becomes `clip-muted.mov`. PATH may be a folder (`-r` for
subfolders). Videos with no sound are skipped with `no sound to remove`.

The file shrinks only by what the sound took up: about 2% on a high-bitrate
phone clip, 15–20% on a low-bitrate screen recording. To make a file small,
use `compress`.

### `vidkit download URL [--quality Q]`

Downloads a video from YouTube, TikTok, Instagram, X, Reddit, Vimeo,
SoundCloud, Twitch and the many other sites yt-dlp supports. `--quality` is
`best` (default) or the tallest picture wanted: `2160`, `1440`, `1080`, `720`,
`480`, `360`. Saves into the current directory, or `--out DIR`, named after the
video's title.

- The file may come out as `.mkv` or `.webm`, because sites serve picture and
  sound separately and they are merged into whatever container fits. If the
  user needs mp4, follow up with `vidkit convert FILE --to mp4`, using the
  `output` path from the report.
- **A playlist link downloads every video in it**, and the report does not
  list them reliably; look in the output folder afterwards. Check with
  `vidkit formats` first: `entries` above 1 means a playlist. Confirm with the
  user before downloading one.
- YouTube radio-mix links (`&list=RD…`) are cut back to the single video
  automatically.

### `vidkit audio URL`

Downloads only the sound, converted to MP3 with tags and cover art.
`--no-mp3` keeps whatever the site serves (often opus in webm).
`--keep-original` keeps that file as well as the MP3.

### `vidkit formats URL`

Looks a link up without downloading: title, uploader, length, playlist size
and every format on offer. Writes nothing.

```json
{
  "command": "formats", "ok": true, "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
  "title": "Me at the zoo", "uploader": "jawed", "duration": 19, "entries": 1,
  "formats": [
    {"id": "133", "ext": "mp4", "resolution": "240p", "fps": "15", "size": "422.9 KB", "kind": "video only"}
  ]
}
```

## Reading the report

`convert`, `compress`, `trim`, `mute`, `download` and `audio` all report the
same way, with one entry per file, including the ones left alone:

```json
{
  "command": "mute",
  "ok": true,
  "counts": {"ok": 2, "skipped": 1, "failed": 0, "over": 0},
  "results": [
    {
      "source": "/Users/me/clips/phone.mp4",
      "output": "/Users/me/clips/converted/phone-muted.mp4",
      "status": "ok",
      "detail": "sound removed, the picture copied untouched",
      "source_bytes": 20591580,
      "output_bytes": 20195066,
      "lossless": true
    },
    {
      "source": "/Users/me/clips/silent.mkv",
      "output": null,
      "status": "skipped",
      "detail": "no sound to remove",
      "source_bytes": 498100,
      "output_bytes": 0,
      "lossless": false
    }
  ]
}
```

| Field | |
|---|---|
| `ok` | `false` when any file failed. Same as exit code 1. |
| `counts` | How many files ended in each status. |
| `status` | `ok`, `skipped`, `failed`, or `over` (compress only: made, but bigger than asked). |
| `detail` | Why, in plain words. The thing to tell the user. |
| `output` | The file made, or `null`. A file skipped because an earlier run already made its output names that file here, so a re-run still tells you where it is. |
| `source` | The file worked on; for a download, the link. |
| `lossless` | `true` when nothing was re-encoded. |
| `title` | Downloads only: the video's title. |

When the work cannot start at all, the report has an `error` in place of
`results`. That happens when ffmpeg is missing, or when `info` or `formats`
cannot read the file or link:

```json
{"command": "info", "ok": false, "error": "Invalid data found when processing input"}
```

Anything else that goes wrong is a `failed` entry in `results`, with the
reason in `detail`. That includes a file that turns out not to be a video and
a link that will not download.

A folder with no videos in it gives `"results": []` and exit code 0.

### What folder runs leave alone

Every file left alone is listed with its reason, so it can be passed on to
the user:

- `no sound to remove` (mute)
- `already mp4` (convert, when nothing would change)
- `clip-muted.mov is already in the output folder`: an earlier run made it
- `another file here also becomes clip.mp4`: two sources would produce the
  same name, such as `Clip.mov` and `clip.mov`
- status `failed`, with ffprobe's reason: the file could not be read

The output folder itself is never scanned, so outputs are not reprocessed.

## Long jobs

`info`, `formats`, `mute`, a fast `trim`, and a `convert` that only copies
streams finish in seconds. `compress`, `trim --exact` and a re-encoding
`convert` decode and encode every frame, which can take minutes for a long or
high-resolution video. Downloads depend on the connection.

Agent shells usually time out after a few minutes. For anything that may run
long, start it in the background (in Claude Code, Bash with
`run_in_background`), or raise the timeout, and read the JSON when it ends. The
output file only appears complete once the command has exited; do not use it
before then.

## Recipes

| The user wants | Command |
|---|---|
| Sound removed from every video in a folder | `vidkit mute DIR -r --json` |
| A video small enough for email or Discord | `vidkit compress FILE --size 25MB --json` |
| A video that plays on an iPhone or Mac | `vidkit convert FILE --to mp4 --json` |
| 1:00 to 1:30 of a clip | `vidkit trim FILE --start 1:00 --end 1:30 --json` |
| The same cut, frame-exact | add `--exact` |
| Whether a video has sound | `vidkit info FILE --json`, check `audio_codec` |
| A YouTube video at 1080p | `vidkit download URL --quality 1080 --json` |
| A song from a link as MP3 | `vidkit audio URL --json` |
| What a link offers, or whether it is a playlist | `vidkit formats URL --json` |
| A download, as mp4 | `download`, then `convert` its `output` with `--to mp4` |
| Muted *and* small | `mute`, then `compress` its `output`, with `--out` naming the folder to keep it tidy |

Each command does one thing, so combining them means feeding one report's
`output` into the next command. When the user asks for two things done to a
file, check whether they mean both applied to one copy or two separate copies,
and ask if it is unclear.

## Telling an agent vidkit exists

Agents only use what they know about. To make vidkit the default for video
work, add this to the project's `CLAUDE.md` or `AGENTS.md`, or to
`~/.claude/CLAUDE.md` for every project:

```markdown
## Video
For converting, compressing, trimming, muting or downloading video, use the
`vidkit` command line, not raw ffmpeg or yt-dlp. Always pass `--json`.
Guide: <toolkit folder>/docs/agents.md
```

Replace `<toolkit folder>` with the folder the toolkit lives in.
