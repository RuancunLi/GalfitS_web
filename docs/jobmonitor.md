# Job Monitor Logic (Implemented State)

## 1. Goal
Build a robust web tracking and overview tool for GalfitS batch workflows that:
1. Reads all target objects from an `.ecsv` catalog.
2. Scans corresponding run folders in a specified workspace to flag "finished/unfinished" targets.
3. Automatically scans for existing `.png` visualizations (`image_fit.png` + `SED_model.png`) to present immediately inline.
4. Allows active inline reviewing where persistent comments can be tied to individual galaxies.
5. Allows users to export lingering datasets logically.

## 2. Core GalfitS Facts Used
1. Central catalog items strictly pull from the first listed column of a standardized `.ecsv` format parsed directly by Astropy Table reading mechanisms.
2. Core success criteria checks existence of `{targ}.gssummary` bound safely under `{workspace}/{targ}/{run_name}/`.
3. Valid preview images map exclusively to hardcoded expectations: `{targ}image_fit.png` and `{targ}SED_model.png`.

## 3. Storage Policy (Important)
1. Job states/images are strictly Read-Only from the core science directory.
2. Comments are stored collectively on disk securely within the workspace parameter bound as `job_monitor_comments_{run_name}.json`.
3. Manual extraction writes directly backwards to parameter sets locally named `job_monitor_unfinished_{run_name}_{timestamp}.json`.
4. Image endpoints serve direct internal assets conditionally allowed via rigid path whitelist definitions.

## 4. Session Model
The state is managed fluidly via Frontend (No intricate session hashing needed):
1. `state.targets` holds complete JSON arrays dictating logic limits locally.
2. `state.zoom`, `state.panX`, and `state.panY` strictly handle layout tracking independently per selected map target.
3. Backend merely scans files statically as directly requested by path strings. 

## 5. API Contract

### POST `/job_monitor/scan`
Input:
```json
{
  "catalog_path": "/path/catalog.ecsv",
  "workspace_path": "/path/galfits/",
  "run_name": "run1"
}
```

Output:
```json
{
  "success": true,
  "catalog_path": "...",
  "workspace_path": "...",
  "run_name": "...",
  "total_targets": 50,
  "unfinished_count": 2,
  "targets": [
    {
      "name": "gal1",
      "lyric_path": "...",
      "summary_path": "...",
      "image_fit_path": "...",
      "has_image": true,
      "finished": true,
      "reviewed": false,
      "comment": ""
    }
  ]
}
```

### GET `/job_monitor/image?path=...`
Simple securely wrapped static file server strictly rendering defined disk images. Validates against rigid domain limits returning `404/403` flags correctly.

### POST `/job_monitor/export_unfinished`
Outputs unresolved arrays into safely timestamped metrics locally in the defined work root path.

### POST `/job_monitor/save_comment`
Merges an incoming user comment directly against the defined internal JSON object database. Modifies/Adds uniquely against the target metric strings strictly checking write abilities globally.

## 6. Frontend Layout Rules
Main workspace divides cleanly into robust side-by-side modules:
1. List Rail (left): Uniquely capped at 360px wide offering a highly scalable Y-axis overflowing target view cleanly with pill status indicators aligned inline.
2. Parameter Viewer (right): Consumes standard `1fr` flexibility displaying preview imagery natively constrained by scaling wrappers logic (`min-height: 260px`).
3. Responsive Design swaps completely down into global full-width blocks if domain hits < 1050px.

## 7. Frontend Interaction Rules
1. Scan Trigger: Culls arrays deeply displaying status summary indicators statically mapping target logic arrays natively down sequentially.
2. Status Pills: Conditionally color-codes "finished/unfinished" natively beside "reviewed/unreviewed" dynamically tracking changes globally.
3. Image Toggling: Instantly switches SED logic cleanly preserving existing dimensions seamlessly to compare branches explicitly.
4. Scale Mechanics: Listens seamlessly onto mouse wheel events (`deltaY`) pushing explicit fractional CSS `transform: translate(x,y) scale(z)` onto the raw DOM limits efficiently bypassing cumbersome graphic canvases.
