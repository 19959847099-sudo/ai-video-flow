# Public presentation assets

The four `screenshots/*-1600x1000.png` files are real captures of the current PySide6 D shell at a 1600×1000 **logical** viewport (2400×1500 physical pixels on the capture machine's 150% DPI display). They use one temporary synthetic project, “雨夜来信”. The local rainy-store demo image already bundled with the app is encoded into a temporary four-second clip and imported as a Candidate; a separate Candidate uses the zero-call video fixture. Neither represents a paid model output. No demo project, personal path, API key or paid-provider response is committed.

Regenerate on Windows with Python dependencies and FFmpeg on `PATH`:

```powershell
python tools/capture_public_screenshots.py
python tools/build_social_preview.py
```

`workflow-overview.svg` is a small editable vector diagram; its accessible description explains the bidirectional Production–Creative collaboration. `social-preview.png` is a standalone 1280×640 PNG composed from the actual Production screenshot. Upload it in the future GitHub repository's Social Preview setting **after** publication is authorized; adding the file here does not set the GitHub account or repository configuration.

When recapturing, inspect all screens for current Product Truth, path/privacy leakage, missing media, legibility and outdated UI. Regenerate the social image after any Production screenshot change. Do not retouch app controls or present local fixture/imported media as commercial model output.
