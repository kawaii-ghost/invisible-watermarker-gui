# ProtectArt

English | [Bahasa Indonesia](README.id.md)

A Tkinter front end for running the [ArtShield invisible watermarker](https://artshield.io/watermarker) locally. Your images are never uploaded anywhere and everything runs on the CPU.

![App screenshot](img/HVWe1BnasAAlh2a.jpg)

> **Important:** this watermark is not strong protection against AI scraping or training. Read [Limitations and Test Results](#limitations-and-test-results) before relying on it.

## Features

- Batch processing with a progress bar.
- Every output is read back and verified automatically. The log shows `[OK]` or `[VERIFY FAILED]` together with the bit accuracy.
- Output formats: PNG, JPEG 4:4:4, and JPEG XL lossless (optional, needs a plugin).
- A **Decode / check** tab to test whether an image still carries the watermark.
- Output files are named `<name>_wm.<ext>`. Existing files are never overwritten.
- Thumbnail preview of the last result.

## Requirements

- Python 3.10 or newer
- `numpy`, `pillow`, `pywavelets`
- `tkinter` (bundled with Python; some Linux distros package it separately)
- Optional: `pillow-jxl-plugin` for reading and writing JPEG XL

## Installation

The watermarking engine is bundled in `third_party/invisible-watermarker/`, so there is nothing else to download.

```bash
git clone <YOUR-REPO-URL>
cd <repo-folder>

pip install numpy pillow pywavelets
pip install pillow-jxl-plugin   # optional, for JPEG XL
```

Repository layout:

```
.
├── protectart.py
├── third_party/
│   └── invisible-watermarker/   # bundled upstream code (MIT), see NOTICE
│       ├── LICENSE
│       └── watermark/
├── NOTICE
├── LICENSE
└── README.md
```

If `tkinter` is missing, install the system package:

```bash
# Fedora
sudo dnf install python3-tkinter
# Debian/Ubuntu
sudo apt install python3-tk
```

On Windows, `tkinter` is normally included in the official Python installer.

## Usage

```bash
python protectart.py
```

**Encode tab**

1. Click **Add images...** and select one or more files.
2. Enter the watermark text (default `SDV2`; ASCII only, 1 to 16 characters).
3. Choose the output format and folder. An empty output folder means results are saved next to the source files.
4. Click **Run** and make sure the log shows `[OK]` for every file.

**Decode / check tab**

1. Select the image you want to inspect.
2. Make sure the watermark text on the Encode tab matches the one used for encoding.
3. Click **Check watermark**. Treat the watermark as readable only when the accuracy is 1.00.

### Output Formats

| Format | Notes |
|---|---|
| PNG | Safe, largest files. |
| JPEG 4:4:4 | Smaller. Chroma subsampling is set to 4:4:4 so the watermark survives. |
| JXL lossless | Needs `pillow-jxl-plugin`. Smaller than PNG, and the watermark stays intact. Lossy JXL is intentionally not offered because results are inconsistent. |

### File Constraints

- Images must be larger than 256×256 pixels and no larger than roughly 4096×4096 pixels. Anything outside that range is rejected.
- Output is always RGB, so the alpha channel is dropped. EXIF metadata and color profiles are not preserved either.

## Limitations and Test Results

This watermark imitates the mark that Stable Diffusion stamps on its own outputs, in the hope that images carrying it get filtered out by dataset curators. There is no evidence that any training pipeline actually filters on this mark, and anyone with the library can read or remove it.

Results from two sample images (600×600 and 1080×1920). Figures are bit accuracy over 32 bits, where 0.5 equals a random guess. Images with no watermark at all score between 0.56 and 0.66.

| Treatment after watermarking | Bit accuracy |
|---|---|
| No change (PNG, JPEG 4:4:4, JXL lossless) | 1.00 |
| JPEG q60 to q95 with 4:4:4 chroma | 1.00 |
| JPEG q75 to q95 with 4:2:0 chroma | 0.59 to 0.72 |
| Resize to 50% | 0.50 to 0.59 |
| Crop of 3% or 8 pixels | 0.38 to 0.41 |
| JXL lossy q95 / q90 / q85 | image-dependent (0.59 to 1.00) |

In short, the watermark only survives if the image is left untouched, or recompressed with JPEG 4:4:4 or lossless JXL. Platforms that recompress with 4:2:0 chroma, resize, or crop will most likely destroy it. Always upload, download the result again, and check it on the Decode tab.

Testing limits: only two images and only Pillow's JPEG encoder, so results on a specific platform may differ.

### Suggested Workflow

If you combine this with other protection tools such as Glaze or Mist, apply the watermark last, because any pixel transformation afterwards can destroy it:

1. Finish the artwork, including cropping and resizing to the upload size.
2. Apply Glaze or Mist.
3. Apply the watermark with this GUI and confirm the log shows `[OK]`.
4. Upload, then check the downloaded copy on the Decode tab.

Combining the watermark with Glaze or Mist has not been tested. Their perturbations may affect watermark detection, so verification is still required.

## How It Works

The core is the same as `EmbedMaxDct` in the `invisible-watermark` library:

1. The image is converted to YUV and only the U (chroma) channel is modified.
2. That channel is decomposed with a Haar DWT, and the LL band is split into 4×4 blocks.
3. Each block stores one bit by quantizing its largest coefficient (step 36). The same bits are repeated across all blocks.
4. When decoding, the results from all blocks are combined by majority vote.

The default payload `SDV2` comes from the official Stable Diffusion 2.x txt2img script. Algorithm details live in the upstream code.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `No module named 'tkinter'` | Install the system package as shown under Installation. |
| `Image is too small` | The image is smaller than 256×256 pixels. |
| JXL option is missing | Run `pip install pillow-jxl-plugin` in the same environment. |
| `[VERIFY FAILED]` | The watermark could not be read after saving. Do not upload that file. Try another format, e.g. PNG. |
| Many `~~~~` lines in the terminal | Debug `print` output from the upstream code. The GUI silences it, but the lines can appear if you run the upstream code directly. |

## Credits and License

- The watermarking engine is the [invisible-watermarker](https://github.com/Alcas1/invisible-watermarker) code by Jonathan Wu and Alice Xie (used on artshield.io), which derives from the [`invisible-watermark`](https://github.com/ShieldMnt/invisible-watermark) library by ShieldMnt. Both are MIT licensed. A copy is bundled in `third_party/invisible-watermarker/`; see [NOTICE](NOTICE) for what was included and removed.
- This project is not affiliated with ArtShield, Stability AI, or the upstream developers.
- Parts of this project were written with AI assistance (Claude, by Anthropic) and reviewed by Kawaii Ghost.
- The GUI file is released under the MIT License (see [LICENSE](LICENSE)). The bundled upstream code keeps its own [LICENSE](third_party/invisible-watermarker/LICENSE). If you redistribute this repository, **keep that file and its copyright notices**.

## Disclaimer

This software is provided as is, without warranty of any kind. No protection tool can guarantee that artwork will not be copied or used for AI training. Treat the watermark as one extra layer, not a replacement for other measures.
