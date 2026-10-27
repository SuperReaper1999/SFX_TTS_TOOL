# SFX TTS Tool

A standalone Windows and Linux (including Kubuntu) utility for building procedural combat, creature, UI, and ambience sound effects, music loops, and spoken dialogue, and exporting them as game-ready WAV files for any engine or audio tool.

Created by [SuperReaper1999](https://github.com/SuperReaper1999) with OpenAI Codex.

## Run

Double-click `Run Sine SFX Designer.bat`, or run:

```powershell
python sine_sfx_designer.py
```

Python 3 must be installed and available on your `PATH`. Install the single DSP dependency once:

```powershell
python -m pip install -r requirements.txt
```

If the window does not open, check that your Python installation includes Tcl/Tk:

```powershell
python -m tkinter
```

That command should open a small Tk demo window. If it reports an `init.tcl` or Tcl/Tk error, repair or reinstall Python with the **tcl/tk and IDLE** optional feature selected; the designer itself needs no Python packages beyond that standard component.

### Linux (Kubuntu)

Install Python, venv, and Tk once:

```bash
sudo apt install python3 python3-venv python3-tk
```

Then run from the tool folder:

```bash
./run-sfx-designer.sh
```

The first run creates a private `.venv` in the tool folder and installs NumPy into it, so nothing is installed system-wide. Previews play through the first available command-line player: `pw-play` (PipeWire, standard on current Kubuntu), `paplay`, `aplay`, or `ffplay`. If none is present, install `pipewire-bin`, `pulseaudio-utils`, or `alsa-utils`. Preset favourites are stored in `~/.config/SfxTtsTool/`.

## Workflow

1. Use the **Design**, **Realism**, and **Mix & Export** tabs to shape the sound.
2. In the **Preset browser**, filter by category, search by name, or save commonly used sounds as favourites. Double-click to load; use **Preview selected** to load and audition a sound in one click.
3. The waveform (peak level over time) and spectrum (average level from 20 Hz to the top of the audible range, on a log scale) update automatically after you pause editing briefly; **Refresh waveform** is still available on demand.
4. Select **Preview** to hear it, then **Stop** to stop playback.
5. Use **Save Project** to retain all editable settings in JSON.
6. Use **Export WAV** and choose any folder. The resulting file is a 44.1 kHz, 16-bit, mono PCM WAV.

Each of the four layers has its own sine, square, triangle, or sawtooth oscillator, frequency, gain, phase, pitch sweep, active start/end time, FM modulation, amplitude LFO, and ADSR envelope. This allows a sharp transient layer to sit above a sustained body or tail.

Use the **Quick global sliders** for fast shaping and the **Quick selected-layer sliders** for frequency, gain, FM depth, and LFO depth. Numeric fields remain available alongside them for exact values; the frequency slider uses a logarithmic scale so low and high frequencies are both practical to adjust.

The Realism tab adds a **High** render quality, which renders at 4× the sample rate and then softly filters back down. It noticeably softens content above about 10 kHz and does not band-limit the square and sawtooth oscillators. It also adds noise in four colours: white (flat), pink (falls 3 dB per octave), brown (falls 6 dB per octave), and band (gently low-passed white). There is one gentle filter (6 dB per octave) with a single **Cutoff Hz** control (0 turns it off) and four modes: low-pass, high-pass, bandpass (which multiplies the low and high bands, so it adds grit), and notch (which cuts high content by the resonance amount). **Resonance** only affects the bandpass and notch modes, and **Filter envelope** shifts the cutoff once, by the sustain level, rather than sweeping it over time. The rest of the tab covers transient bursts, pitch drift and jitter, formant tones (ring modulation at the chosen frequencies, which gives a metallic, vocal-ish edge rather than true vowel filtering), soft distortion, feedback delay, and a short room effect of four early echoes within about 0.1 s rather than a long reverb tail. These are tuned for weapon impacts and zombie vocalisations while retaining mono output that suits positional audio in game engines.

## Preset browser

The preset browser keeps the built-in library out of the way of the design controls while making it quick to reuse. Filter by category, type part of a preset or category name, and use **Add favourite** for frequently used sounds. Favourites are stored locally in your Windows app-data folder (or `~/.config/SfxTtsTool` on Linux; favourites saved under the old `UnitySfxDesigner` folder are still read), so updating the tool does not alter your project files or Git working tree.

## Piano roll

The **Piano** tab is a four-track game-music sequencer. Give each track a name, choose either the current design or a built-in preset as its instrument (pitched instruments are tuned so their loudest layer plays the written note, while drum presets and designs with no oscillator layers play at their natural pitch on C4, like a sampler), adjust its volume, and mute it independently. **Edit** selects the track you change; **Show** overlays any number of tracks in the grid, using a distinct colour for each. Click cells to add/remove notes, or drag across cells to set a note length. The **Current-design wave** selector provides an immediate sine/square/triangle/sawtooth change for every enabled oscillator used by Custom tracks. Set the BPM, choose an 8-, 16-, or 32-step loop, then preview or export the complete loop as a game-ready WAV. **Load minor loop** and **Load major loop** replace only the note pattern on the selected track; they preserve every track and project setting.

Music notes, tempo, and loop length are saved in normal project JSON files alongside the synth settings. This is deliberately a compact sequencer for loops, stings, and menu music—not a replacement for a full DAW. Exported music remains mono to suit positional or UI playback; use the same project’s effects controls to shape the instrument and room tail.

## Variations

Use **Export Variations** to build 2–50 related WAVs from the current design. The **Variation %** setting controls how much pitch, gain, timing, sweep, phase, and noise seed differ. This is ideal for avoiding repetitive footsteps, impacts, gunshot layers, and zombie sounds while keeping a coherent sound family.

## Sound Packs

Use **Export Sound Pack** to write one or more game-ready WAVs and a matching `.sfx.json` recipe to one folder. Keep the JSON next to its exported audio to make future tuning reproducible; the folder can then be copied straight into your game project.

## Validate without opening the UI

```powershell
python sine_sfx_designer.py --self-test
```

On Linux: `./run-sfx-designer.sh --self-test`

This exports every built-in preset to a temporary location and verifies the required WAV format (44.1 kHz, 16-bit, mono PCM).

## Dialogue Studio (free local Kokoro TTS)

The **Dialogue Studio** tab turns quest dialogue into WAV files with the free local Kokoro model. Add one line or queue a batch, choose a character profile/voice, choose a pace, and generate the WAVs into an output folder. It writes `dialogue_manifest.json` beside the audio, preserving the speaker, line ID, text, voice, speed, and filename so each clip can be matched to its dialogue line in your game. Generating more lines into the same folder adds them to that manifest, and regenerating a line updates its existing entry.

Kokoro loads once per session: Dialogue Studio starts it in the background when you first open the tab, and keeps it running until you close the app. After that start (around 10 seconds on a typical CPU), each line takes about a second instead of reloading the model every time. If Kokoro fails, details are written to `.kokoro-cache/kokoro_worker.log`.

The queue and output folder are saved automatically and restored next time you open the tool. Adding a line clears the text box and moves the line ID on to the next number (`autumn_intro_01` → `autumn_intro_02`).

### Speaker profiles

A profile remembers a speaker's Kokoro voice and character notes. Pick one to fill in its voice and notes, or type a new speaker name, set the voice and notes, and select **Save Profile**. **Delete Profile** removes the selected one; queued lines keep their own voice. Profiles are stored in your settings folder (`%APPDATA%\SfxTtsTool` on Windows, `~/.config/SfxTtsTool` on Linux) along with the saved queue.

### Importing a script

**Import Script…** adds a whole scene to the queue from a text or CSV file.

A text script has one line of dialogue per line, written `Speaker: what they say`. Lines without a speaker use the currently selected speaker, and blank lines and lines starting with `#` are skipped:

```text
# Intro scene
Autumn: Stay close. Whatever is out there heard the gunshot.
Reeves: Right then. Kettle on, and nobody opens that door.
```

A CSV needs a header row with a `text` column, and can also have `speaker`, `line_id`, `voice`, `speed`, and `notes` columns:

```text
speaker,line_id,text,voice,speed
Narrator,narr_open,The town fell quiet before dawn.,,0.9
```

Empty voice and notes come from the speaker's profile. Lines without an ID are numbered per speaker (`autumn_01`, `autumn_02`, …), skipping IDs already queued. A line with an explicit ID replaces the queued line with the same speaker and ID, so you can edit a script and import it again.

There is no API key, OpenAI account, or per-line bill. Kokoro runs locally after its one-time download. Its Apache-2.0 model weighs roughly 363 MB, so it is deliberately kept out of the repository and C: drive.

### One-time local setup — S: only

Double-click `Install Local Kokoro TTS.bat` in this tool folder. It installs Kokoro and its Python dependencies into:

```text
S:\Repos\SFX_TTS_TOOL\.local-tts
```

The first generated line downloads the model into:

```text
S:\Repos\SFX_TTS_TOOL\.kokoro-cache
```

The installer sets its package, download, temporary, and model locations beneath this tool folder. It does not use C: for the installation or model cache. The download needs internet once; generation is offline afterwards.

### Linux setup

Run `./run-sfx-designer.sh` once (to create `.venv`), then:

```bash
./install-local-kokoro-tts.sh
```

This installs Kokoro into `.local-tts` inside the tool folder, and the model downloads into `.kokoro-cache` on the first generated line, just as on Windows. Kokoro supports Python 3.10–3.12 only. If your system Python is newer, unpack a standalone Python 3.12 (for example an `install_only` build from [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases)) into `.python312` in the tool folder, so that `.python312/bin/python3` exists. The installer and Dialogue Studio both use it automatically, while the designer itself keeps running on your system Python. On Linux, pip's default PyTorch build includes NVIDIA CUDA libraries and is several gigabytes. If you only want the smaller CPU build, run `PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu ./install-local-kokoro-tts.sh`.

### Recommended game workflow

1. Give each spoken dialogue line a stable ID such as `autumn_intro_01`.
2. Generate the matching WAV file in Dialogue Studio.
3. Copy the generated folder into your game project's assets.
4. Assign each imported WAV to the dialogue line with the matching ID. Keep `dialogue_manifest.json` alongside the clips as the line-to-file reference.
