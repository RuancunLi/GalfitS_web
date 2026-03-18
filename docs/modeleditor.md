# GS Editor Logic (Implemented State)

## 1. Goal
Build a web editor for GalfitS that:
1. Loads a `.lyric` by absolute server path.
2. Creates one persistent `Myfitter` session per load.
3. Displays current fit overview image from GalfitS standard workflow.
4. Lets user edit only variable parameters (`Myfitter.varnames`).
5. Recalculates and refreshes figure/parameters after submit.

## 2. Core GalfitS Facts Used
1. `gsutils.read_config_file(...)` returns `Myfitter` and context.
2. `Myfitter` contains complete model/data state (`GSdata`, `model_list`, `mtype_list`, `pardict`, `varnames`, etc.).
3. Visualization is generated using `gsutils.standard_display(...)`.
4. Standard display writes output files in workplace:
   - `{targ}image_fit.png`
   - `{targ}SED_model.png` (when SED branch exists)
5. Galaxy subcomponents are defined by `model.subnames` where `mtype_list[i] == 'galaxy'`.

## 3. Storage Policy (Important)
1. No preview images are stored in GS_editor repo static directory.
2. Preview files are written in lyric/workplace directory by GalfitS itself.
3. File names are fixed and overwritten each run (no indexed temp copies).

## 4. Session Model
Backend keeps in-memory cache keyed by `session_id`:
1. `Myfitter`
2. `workplace`
3. `targ`
4. `image_path` (`{targ}image_fit.png`)
5. `sed_image_path` (`{targ}SED_model.png`)
6. `has_sed_image`

This avoids re-reading lyric for every parameter update.

## 5. API Contract

### POST `/upload`
Input:
```json
{"lyric_path": "/absolute/path/to/file.lyric"}
```

Validation:
1. Absolute path only.
2. Must end with `.lyric`.
3. Must exist.
4. Must be under allowed roots.

Output:
```json
{
  "success": true,
  "session_id": "...",
  "preview_url": "/preview_image/<session_id>",
  "parameters_tree": [...],
  "nimage": 12,
  "has_sed_image": true
}
```

### POST `/update_parameters`
Input:
```json
{
  "session_id": "...",
  "updates": {
    "param_key": "new_value"
  }
}
```

Behavior:
1. Apply only keys in `Myfitter.varnames`.
2. Coerce types based on current `pardict` value type.
3. Recalculate model (`cal_model` if available, otherwise `cal_model_image(pardict=...)`).
4. Re-run standard display.

Output shape is same as `/upload` (refreshed preview/parameters).

### GET `/preview_image/<session_id>?kind=fit|sed`
1. `kind=fit` serves current `{targ}image_fit.png`.
2. `kind=sed` serves `{targ}SED_model.png`.
3. Security: path must pass allowed-root check.

## 6. Parameter Tree Rules
Only editable vars are included:
1. Source set = `Myfitter.varnames`.

Categorization priority:
1. Galaxy subcomponent match first:
   - For all galaxy models, if varname matches a `subname` token (start/end/underscore-boundary), assign to that subcomponent.
2. Then model-level match by model name.
3. Remaining vars go to `global` bucket.

Each parameter node contains:
1. `full_key` (submit key)
2. `name` (display)
3. `value` (stringified)

## 7. Frontend Layout Rules
Single-screen workspace with adaptive split:
1. If `nimage <= 16`: left/right mode (preview 50%, parameters 50%).
2. If `nimage > 16`: top/bottom mode.

Parameter density:
1. Right half mode: 3 parameter entries per row.
2. Bottom mode: 7 parameter entries per row.
3. On small screens, responsive fallback reduces columns.

## 8. Frontend Interaction Rules
1. Load lyric:
   - set `session_id`
   - show fit preview image
   - render parameter tree
2. Submit updates:
   - send all edited `full_key -> value`
   - refresh preview and parameter tree
3. SED toggle:
   - button shown only when `has_sed_image=true`
   - toggles between FIT and SED preview in same panel

## 9. Styling Adjustments Already Applied
1. Parameter label font reduced by 30%.
2. Parameter textbox width reduced by 35% (to 65%).

## 10. Known Remaining Risks
1. `cal_model` method may differ by fitter subclass; current fallback to `cal_model_image` keeps compatibility.
2. Type coercion for complex string/list parameters may need tighter schema-specific parser.
3. Session cache is in-memory only (no persistence across process restart).

## 11. Acceptance Checklist
1. Loading lyric works with relative resource paths.
2. Preview files are written in lyric folder, not repo static uploads.
3. FIT/SED toggle works when SED figure exists.
4. Only `varnames` parameters are editable.
5. `AVbump_bulge`-like keys are categorized under `bulge`, not global.
6. Parameter grid density follows 3-column (right mode) / 7-column (bottom mode).
