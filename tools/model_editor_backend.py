from __future__ import annotations

import os
import uuid
from typing import Any

import matplotlib
import numpy as np
from flask import jsonify, request, send_file
from galfits import gsutils

# Non-interactive backend prevents macOS NSException crashes.
matplotlib.use('Agg', force=True)


_SESSION_CACHE: dict[str, dict[str, Any]] = {}


def _stringify_value(value: Any) -> str:
    if hasattr(value, 'value'):
        value = value.value
    if isinstance(value, np.ndarray):
        return np.array2string(value, precision=6, separator=',')
    return str(value)


def _belongs_to_model(param_key: str, model_name: str) -> bool:
    return (
        param_key == model_name
        or param_key.startswith(f'{model_name}_')
        or param_key.endswith(f'_{model_name}')
        or f'_{model_name}_' in param_key
    )


def _subname_match(param_key: str, subname: str) -> bool:
    key = param_key.lower()
    sub = str(subname).lower()
    return (
        key.startswith(sub)
        or key.endswith(sub)
        or f'_{sub}_' in key
        or f'_{sub}' in key
        or f'{sub}_' in key
    )


def _coerce_value(raw_value: str, template: Any) -> Any:
    if isinstance(template, (np.floating, float)):
        return float(raw_value)
    if isinstance(template, (np.integer, int)) and not isinstance(template, bool):
        return int(float(raw_value))
    if isinstance(template, (np.bool_, bool)):
        text = raw_value.strip().lower()
        return text in {'1', 'true', 't', 'yes', 'y'}
    if isinstance(template, np.ndarray):
        text = raw_value.strip()
        if text.startswith('[') and text.endswith(']'):
            text = text[1:-1]
        items = [it.strip() for it in text.split(',') if it.strip()]
        if len(items) == 0:
            return np.array([], dtype=template.dtype)
        return np.array([float(it) for it in items], dtype=template.dtype)
    return raw_value


def _build_parameters_tree(Myfitter) -> list[dict[str, Any]]:
    pardict = dict(getattr(Myfitter, 'pardict', {}) or {})
    varnames = set(str(v) for v in (getattr(Myfitter, 'varnames', []) or []))
    tree: list[dict[str, Any]] = []

    model_list = list(getattr(Myfitter, 'model_list', []) or [])
    mtype_list = list(getattr(Myfitter, 'mtype_list', []) or [])
    node_index: dict[str, tuple[dict[str, Any], dict[str, list[dict[str, str]]]]] = {}

    for idx, model in enumerate(model_list):
        model_name = str(getattr(model, 'name', getattr(model, 'prefix', f'model_{idx}')))
        model_type = str(mtype_list[idx]) if idx < len(mtype_list) else 'unknown'
        node: dict[str, Any] = {
            'model_name': model_name,
            'model_type': model_type,
            'parameters': [],
            'subcomponents': [],
        }

        sub_map: dict[str, list[dict[str, str]]] = {}
        if model_type == 'galaxy':
            for sub in list(getattr(model, 'subnames', []) or []):
                sub_map[str(sub)] = []

        tree.append(node)
        node_index[model_name] = (node, sub_map)

    global_params: list[dict[str, str]] = []

    for key, value in pardict.items():
        key_str = str(key)
        if key_str not in varnames:
            continue

        entry = {
            'full_key': key_str,
            'name': key_str,
            'value': _stringify_value(value),
        }

        sub_candidates: list[tuple[int, str, str]] = []
        for model_name, (node, sub_map) in node_index.items():
            if node['model_type'] != 'galaxy':
                continue
            for subname in sub_map:
                if _subname_match(key_str, subname):
                    score = 1
                    if _belongs_to_model(key_str, model_name):
                        score += 2
                    sub_candidates.append((score, model_name, subname))

        if len(sub_candidates) > 0:
            sub_candidates.sort(key=lambda item: item[0], reverse=True)
            _, model_name, subname = sub_candidates[0]
            node, sub_map = node_index[model_name]
            sub_map[subname].append(entry)
            continue

        model_candidates: list[str] = []
        for model_name, _ in node_index.items():
            if _belongs_to_model(key_str, model_name):
                model_candidates.append(model_name)

        if len(model_candidates) > 0:
            model_name = model_candidates[0]
            node, _ = node_index[model_name]
            node['parameters'].append(entry)
            continue

        global_params.append(entry)

    for _, (node, sub_map) in node_index.items():
        for subname, params in sub_map.items():
            params.sort(key=lambda item: item['name'])
            node['subcomponents'].append({'name': subname, 'parameters': params})

        node['parameters'].sort(key=lambda item: item['name'])

    global_params.sort(key=lambda item: item['name'])
    if global_params:
        tree.append({
            'model_name': 'global',
            'model_type': 'global',
            'parameters': global_params,
            'subcomponents': [],
        })

    return tree


def _load_fitter_from_lyric(file_path: str):
    lyric_dir = os.path.dirname(os.path.abspath(file_path))
    old_cwd = os.getcwd()
    os.chdir(lyric_dir)
    try:
        Myfitter, targ, fs = gsutils.read_config_file(file_path, lyric_dir)
        return Myfitter, targ, lyric_dir
    finally:
        os.chdir(old_cwd)


def _render_display_image(Myfitter, workplace: str, targ: str) -> str:
    old_cwd = os.getcwd()
    os.chdir(workplace)
    try:
        gsutils.standard_display(Myfitter, workplace, targ)
    finally:
        os.chdir(old_cwd)
    return os.path.join(workplace, f'{targ}image_fit.png')


def _apply_parameter_updates(Myfitter, updates: dict[str, str]) -> dict[str, Any]:
    current = dict(getattr(Myfitter, 'pardict', {}) or {})
    allowed = set(str(v) for v in (getattr(Myfitter, 'varnames', []) or []))
    for key, value in (updates or {}).items():
        if key not in current:
            continue
        if key not in allowed:
            continue
        current[key] = _coerce_value(str(value), current[key])

    # Follow requested workflow when available.
    if hasattr(Myfitter, 'cal_model') and callable(getattr(Myfitter, 'cal_model')):
        Myfitter.cal_model(current)
    else:
        Myfitter.cal_model_image(pardict=current)

    Myfitter.pardict = current
    return current


def _build_editor_payload(Myfitter, workplace: str, targ: str) -> dict[str, Any]:
    image_path = _render_display_image(Myfitter, workplace, targ)
    sed_image_path = os.path.join(workplace, f'{targ}SED_model.png')
    parameters_tree = _build_parameters_tree(Myfitter)
    nimage = int(getattr(getattr(Myfitter, 'GSdata', None), 'Nimages', 0) or 0)
    return {
        'image_path': image_path,
        'sed_image_path': sed_image_path,
        'has_sed_image': os.path.isfile(sed_image_path),
        'parameters_tree': parameters_tree,
        'nimage': nimage,
    }


def register_model_editor_routes(app, is_allowed_path_func):
    @app.route('/model_editor/upload', methods=['POST'])
    def model_editor_upload():
        payload = request.get_json(silent=True) or {}
        lyric_path = str(payload.get('lyric_path', '')).strip()

        if not lyric_path:
            return jsonify({'success': False, 'message': 'Missing lyric_path.'}), 400
        if not os.path.isabs(lyric_path):
            return jsonify({'success': False, 'message': 'Please provide an absolute .lyric path.'}), 400
        if not lyric_path.endswith('.lyric'):
            return jsonify({'success': False, 'message': 'Invalid file format. Please provide a .lyric path.'}), 400
        if not is_allowed_path_func(lyric_path):
            return jsonify({'success': False, 'message': 'Access denied: path must be in allowed directories.'}), 403
        if not os.path.isfile(lyric_path):
            return jsonify({'success': False, 'message': f'File not found: {lyric_path}'}), 400

        try:
            Myfitter, targ, workplace = _load_fitter_from_lyric(lyric_path)
            payload_out = _build_editor_payload(Myfitter, workplace, targ)

            session_id = str(uuid.uuid4())
            _SESSION_CACHE[session_id] = {
                'Myfitter': Myfitter,
                'targ': targ,
                'workplace': workplace,
                'lyric_path': lyric_path,
                'image_path': payload_out['image_path'],
                'sed_image_path': payload_out['sed_image_path'],
                'has_sed_image': payload_out['has_sed_image'],
            }

            return jsonify({
                'success': True,
                'session_id': session_id,
                'preview_url': f'/model_editor/preview_image/{session_id}',
                'parameters_tree': payload_out['parameters_tree'],
                'nimage': payload_out['nimage'],
                'has_sed_image': payload_out['has_sed_image'],
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/model_editor/update_parameters', methods=['POST'])
    def model_editor_update_parameters():
        payload = request.get_json(silent=True) or {}
        session_id = str(payload.get('session_id', '')).strip()
        updates = payload.get('updates', {})

        if not session_id:
            return jsonify({'success': False, 'message': 'Missing session_id.'}), 400
        if session_id not in _SESSION_CACHE:
            return jsonify({'success': False, 'message': 'Session not found or expired.'}), 404
        if not isinstance(updates, dict):
            return jsonify({'success': False, 'message': 'updates must be a key-value object.'}), 400

        try:
            ctx = _SESSION_CACHE[session_id]
            _apply_parameter_updates(ctx['Myfitter'], updates)
            refreshed = _build_editor_payload(ctx['Myfitter'], ctx['workplace'], ctx['targ'])
            ctx['image_path'] = refreshed['image_path']
            ctx['sed_image_path'] = refreshed['sed_image_path']
            ctx['has_sed_image'] = refreshed['has_sed_image']

            return jsonify({
                'success': True,
                'session_id': session_id,
                'preview_url': f'/model_editor/preview_image/{session_id}',
                'parameters_tree': refreshed['parameters_tree'],
                'nimage': refreshed['nimage'],
                'has_sed_image': refreshed['has_sed_image'],
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/model_editor/preview_image/<session_id>', methods=['GET'])
    def model_editor_preview_image(session_id):
        ctx = _SESSION_CACHE.get(session_id)
        if ctx is None:
            return jsonify({'success': False, 'message': 'Session not found or expired.'}), 404

        kind = str(request.args.get('kind', 'fit')).strip().lower()
        if kind == 'sed':
            image_path = str(ctx.get('sed_image_path', ''))
        else:
            image_path = str(ctx.get('image_path', ''))

        if not image_path:
            return jsonify({'success': False, 'message': 'No preview image available.'}), 404

        image_path = os.path.abspath(image_path)
        if not is_allowed_path_func(image_path):
            return jsonify({'success': False, 'message': 'Access denied.'}), 403
        if not os.path.isfile(image_path):
            return jsonify({'success': False, 'message': f'Preview file not found: {image_path}'}), 404
        return send_file(image_path, mimetype='image/png')
