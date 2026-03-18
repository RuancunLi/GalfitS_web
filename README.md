# GalfitS Web Tools

A collection of web-based interactive tools for the GalfitS fitting workflow. This repository provides a modern, user-friendly interface for image inspection, job monitoring, and model parameter editing.

## Tools Overview

### 1. Image Previewer
An interactive FITS image viewer that allows users to:
- Load images via local upload or absolute server paths.
- Perform coordinate-based image cuts (RA/DEC).
- Interactively inspect pixel coordinates and local peaks using a draggable crosshair.
- View real-time dRA/dDec offsets in arcseconds.

### 2. Job Monitor
A dashboard for tracking the progress of batch GalfitS runs:
- Scan workspaces for completed targets based on an ECSV catalog.
- Preview fit results (`image_fit.png`) and SED models (`SED_model.png`) inline.
- Add and save persistent review comments for each target.
- Export lists of unfinished targets for subsequent re-runs.

### 3. Model Editor
A dedicated tool for fine-tuning GalfitS model parameters:
- Load `.lyric` configuration files from absolute paths.
- Edit variable parameters organized by model component and subcomponent (e.g., bulge, disk).
- Trigger on-the-fly model recalculations and refresh visual previews immediately.
- Adaptive layout adjusts to the number of images (Single-screen split or stacked modes).

## Getting Started

### Prerequisites
- Python 3.x
- Dependencies: `flask`, `numpy`, `matplotlib`, `astropy`, `reproject`, `jax` (and `galfits` library).

### Installation
```bash
pip install -r requirements.txt
```

### Running the App
Start the Flask development server:
```bash
python app.py
```
Access the tools at `http://localhost:6002`.

## Documentation
Detailed logic and implementation details for each tool can be found in the `docs/` directory:
- [Image Previewer Logic](docs/imagepreviewer.md)
- [Job Monitor Logic](docs/jobmonitor.md)
- [Model Editor Logic](docs/modeleditor.md)
