# Image Previewer Logic (Implemented State)

## 1. Goal
Build a web interactive image viewer for GalfitS that:
1. Loads an image from an uploaded `.fits` file or an absolute server path.
2. Performs a central cut using target RA, DEC, layer, and cut radius parameters.
3. Displays the synthesized cut image with an interactive crosshair/draggable area.
4. Analyzes and returns live mouse tracking coordinates and local peaks via API polling.

## 2. Core GalfitS Facts Used
1. `IM.image(...)` is invoked to load HDU data arrays and implicitly binds to `cR` units.
2. `img.img_cut(ra, dec, cut_radius)` generates a sliced subset map (`imcut`) alongside its coordinate parameters.
3. Transformation `gala.coordinates_transfer_inverse` is used to directly map pixel bounds backwards to dRA and dDec metrics.
4. `peak_finder` function executes a local gradient check within a 15 pixel radial window from the clicked target.

## 3. Storage Policy (Important)
1. Uploaded mock-files are written to standard system temporary directories (e.g. `/tmp`) uniquely keyed via UUID, and cleanly discarded downstream.
2. Server file paths directly circumvent uploads, securely filtered against defined root bounds.
3. Cut datasets strictly live inside in-memory mappings; no cut snippets are permanently preserved to local disks.

## 4. Session Model
The backend relies on an active RAM dictionary `image_store` scoped tightly by a unique `image_id`:
1. `img` (base FITS Image object instance)
2. `imcut`, `header`, `cp` 
3. Display boundaries: `immin`, `immax`, `sky_median`
4. Context keys: `ra`, `dec`, `cut_radius`
5. Cleanup tag: `is_temp_file`

## 5. API Contract

### POST `/load_image`
Input: Form Data
- `ra`, `dec`, `layer`, `cut_radius`
- Multiparter File `file` OR String `file_path`

Output:
```json
{
  "success": true,
  "image_id": "...",
  "image_shape": [ny, nx]
}
```

### GET `/get_image/<image_id>`
1. Generates and buffers an inline Matplotlib `.png` slice on demand.
2. Strips all inherent matplotlib axes and paddings so coordinates flawlessly map to the frontend elements.

### POST `/get_coordinates`
Input:
```json
{
  "image_id": "...",
  "pixel_x": 150,
  "pixel_y": 150
}
```
Output:
```json
{
  "mouse_pixel_x": 150,
  "mouse_pixel_y": 150,
  "mouse_delta_ra": 0.05,
  "mouse_delta_dec": -0.1,
  "peak_pixel_x": 151,
  "peak_pixel_y": 151,
  "peak_delta_ra": 0.055,
  "peak_delta_dec": -0.102
}
```

### DELETE `/cleanup/<image_id>`
Purges dictionary cache and wipes temp uploads gracefully.

## 6. Frontend Layout Rules
Inputs sit rigidly atop a central display layout:
1. Mode toggling (Upload vs Path) dynamically swaps input branches in DOM.
2. Display image automatically scales `max-width: 100%` remaining strictly bordered to avoid layout explosions.
3. An active info-panel gracefully scales from `1fr 1fr` dual-column on Desktop to `1fr` stacked block on devices under 900px width.

## 7. Frontend Interaction Rules
1. Submit Load Action: Blocks UI via disabled loads and presents a spinning loading state gracefully. Automatically calculates core coordinate arrays via image dimensions to set initial crosshair mapping.
2. Native Image Hovering: CSS tracks `draggableArea` translating the `mousemove` actions seamlessly over to coordinate percentages inside pure JS (no heavy libraries needed).
3. Active Updates: Binds coordinate payload returns natively to decoupled text spans.
4. Resize Hooks: Updates crosshair proportional layout whenever the core browser limits are disrupted to prevent ghost drift.
