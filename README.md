# Unity SFX Designer

A standalone Windows and Linux (including Kubuntu) utility for building procedural combat, creature, UI, and ambience sound effects and exporting them as Unity-ready WAV files.

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

The first run creates a private `.venv` in the tool folder and installs NumPy into it, so nothing is installed system-wide. Previews play through the first available command-line player: `pw-play` (PipeWire, standard on current Kubuntu), `paplay`, `aplay`, or `ffplay`. If none is present, install `pipewire-bin`, `pulseaudio-utils`, or `alsa-utils`. Preset favourites are stored in `~/.config/UnitySfxDesigner/`.

## Workflow

1. Use the **Design**, **Realism**, and **Mix & Export** tabs to shape the sound.
2. In the **Preset browser**, filter by category, search by name, or save commonly used sounds as favourites. Double-click to load; use **Preview selected** to load and audition a sound in one click.
3. The waveform and spectrum update automatically after you pause editing briefly; **Refresh waveform** is still available on demand.
4. Select **Preview** to hear it, then **Stop** to stop playback.
5. Use **Save Project** to retain all editable settings in JSON.
6. Use **Export WAV** and choose any folder. The resulting file is a 44.1 kHz, 16-bit, mono PCM WAV.

Each of the four layers has its own sine, square, triangle, or sawtooth oscillator, frequency, gain, phase, pitch sweep, active start/end time, FM modulation, amplitude LFO, and ADSR envelope. This allows a sharp transient layer to sit above a sustained body or tail.

Use the **Quick global sliders** for fast shaping and the **Quick selected-layer sliders** for frequency, gain, FM depth, and LFO depth. Numeric fields remain available alongside them for exact values; the frequency slider uses a logarithmic scale so low and high frequencies are both practical to adjust.

The Realism tab adds 4× oversampled rendering, white/pink/brown/band-limited noise, resonant filter modes, transient bursts, pitch drift/jitter, formant bands, soft distortion, feedback delay, and a compact mono room tail. These are tuned for weapon impacts and zombie vocalisations while retaining Unity-friendly mono positional audio.

## Preset browser

The preset browser keeps the built-in library out of the way of the design controls while making it quick to reuse. Filter by category, type part of a preset or category name, and use **Add favourite** for frequently used sounds. Favourites are stored locally in your Windows app-data folder (or `~/.config/UnitySfxDesigner` on Linux), so updating the tool does not alter your project files or Git working tree.

## Piano roll

The **Piano** tab is a four-track game-music sequencer. Give each track a name, choose either the current design or a built-in preset as its instrument, adjust its volume, and mute it independently. **Edit** selects the track you change; **Show** overlays any number of tracks in the grid, using a distinct colour for each. Click cells to add/remove notes, or drag across cells to set a note length. The **Current-design wave** selector provides an immediate sine/square/triangle/sawtooth change for every enabled oscillator used by Custom tracks. Set the BPM, choose an 8-, 16-, or 32-step loop, then preview or export the complete loop as a Unity-ready WAV. **Load minor loop** and **Load major loop** replace only the note pattern on the selected track; they preserve every track and project setting.

Music notes, tempo, and loop length are saved in normal project JSON files alongside the synth settings. This is deliberately a compact sequencer for loops, stings, and menu music—not a replacement for a full DAW. Exported music remains mono to suit Unity positional or UI playback; use the same project’s effects controls to shape the instrument and room tail.

## Variations

Use **Export Variations** to build 2–50 related WAVs from the current design. The **Variation %** setting controls how much pitch, gain, timing, sweep, phase, and noise seed differ. This is ideal for avoiding repetitive footsteps, impacts, gunshot layers, and zombie sounds while keeping a coherent sound family.

## Unity Packs

Use **Export Unity Pack** to write one or more Unity-ready WAVs and a matching `.sfx.json` recipe to one folder. Keep the JSON next to its exported audio to make future tuning reproducible; either folder can then be copied directly beneath a Unity project's `Assets` folder.

## Validate without opening the UI

```powershell
python sine_sfx_designer.py --self-test
```

On Linux: `./run-sfx-designer.sh --self-test`

This exports every built-in preset to a temporary location and verifies the required Unity WAV format.

## Dialogue Studio (free local Kokoro TTS)

The **Dialogue Studio** tab turns quest dialogue into WAV files with the free local Kokoro model. Add one line or queue a batch, choose a character profile/voice, choose a pace, and generate the WAVs into an output folder. It writes `dialogue_manifest.json` beside the audio, preserving the speaker, line ID, text, voice, speed, and filename for assignment to Unity `DialogueNode` assets.

There is no API key, OpenAI account, or per-line bill. Kokoro runs locally after its one-time download. Its Apache-2.0 model weighs roughly 363 MB, so it is deliberately kept out of the repository and C: drive.

### One-time local setup — S: only

Double-click `Install Local Kokoro TTS.bat` in this tool folder. It installs Kokoro and its Python dependencies into:

```text
S:\Repos\Unity-SFX-Designer\.local-tts
```

The first generated line downloads the model into:

```text
S:\Repos\Unity-SFX-Designer\.kokoro-cache
```

The installer sets its package, download, temporary, and model locations beneath this tool folder. It does not use C: for the installation or model cache. The download needs internet once; generation is offline afterwards.

### Linux setup

Run `./run-sfx-designer.sh` once (to create `.venv`), then:

```bash
./install-local-kokoro-tts.sh
```

This installs Kokoro into `.local-tts` inside the tool folder, and the model downloads into `.kokoro-cache` on the first generated line, just as on Windows. Kokoro supports Python 3.10–3.12 only. If your system Python is newer, unpack a standalone Python 3.12 (for example an `install_only` build from [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases)) into `.python312` in the tool folder, so that `.python312/bin/python3` exists. The installer and Dialogue Studio both use it automatically, while the designer itself keeps running on your system Python. On Linux, pip's default PyTorch build includes NVIDIA CUDA libraries and is several gigabytes. If you only want the smaller CPU build, run `PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu ./install-local-kokoro-tts.sh`.

### Recommended Unity workflow

1. Give each spoken `DialogueNode` line a stable ID such as `autumn_intro_01`.
2. Generate the matching WAV file in Dialogue Studio.
3. Copy the generated folder beneath your Unity project's `Assets` directory.
4. Assign the imported WAV clips to the matching dialogue-line voice clip slots. Keep `dialogue_manifest.json` alongside the clips as the line-to-file reference.
