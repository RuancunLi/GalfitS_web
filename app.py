from flask import Flask, request, jsonify, send_file, send_from_directory
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from astropy.table import Table
from astropy import units as u
from astropy.cosmology import FlatLambdaCDM,z_at_value
from astropy.io import fits,ascii
from astropy.time import Time
import os,shutil
os.environ['XLA_PYTHON_CLIENT_PREALLOCATE'] = 'false'
import galfits.images as IM
import galfits.galaxy as gala
from galfits import gsutils
from galfits.mathfunc import Maskellipse
import galfits.profiles as prof
from astropy.stats import sigma_clipped_stats
from reproject import reproject_exact, reproject_adaptive
import jax.numpy as jnp
import uuid
import tempfile
from io import BytesIO
import base64
import json
from datetime import datetime, timezone
from image_preview import peak_finder
from tools.model_editor_backend import register_model_editor_routes

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Store image data in memory (in production, use a proper database)
image_store = {}


def _is_allowed_path(path: str) -> bool:
    abs_path = os.path.abspath(path)
    allowed_roots = ['/Users/liruancun/', '/home/liruancun/']
    return any(abs_path.startswith(root) for root in allowed_roots)


def _read_target_names(catalog_path: str) -> list[str]:
    tab = Table.read(catalog_path, format='ascii.ecsv')
    if len(tab.colnames) == 0:
        raise ValueError('Catalog has no columns.')
    first_col = tab.colnames[0]
    return [str(name).strip() for name in tab[first_col]]


def _comments_file_path(workspace_path: str, run_name: str) -> str:
    safe_run = run_name.strip().replace('/', '_')
    return os.path.join(workspace_path, f'job_monitor_comments_{safe_run}.json')


def _load_comments(workspace_path: str, run_name: str) -> dict[str, dict[str, str]]:
    comments_path = _comments_file_path(workspace_path, run_name)
    if not os.path.exists(comments_path):
        return {}
    try:
        with open(comments_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        return {}
    return {}


def _write_json(path: str, payload: dict) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _build_job_monitor_rows(catalog_path: str, workspace_path: str, run_name: str) -> list[dict]:
    target_names = _read_target_names(catalog_path)
    comments = _load_comments(workspace_path, run_name)
    rows: list[dict] = []
    for name in target_names:
        target_dir = os.path.join(workspace_path, name)
        run_dir = os.path.join(target_dir, run_name)
        lyric_path = os.path.join(target_dir, f'{run_name}.lyric')
        summary_path = os.path.join(run_dir, f'{name}.gssummary')
        image_fit_path = os.path.join(run_dir, f'{name}image_fit.png')
        sed_model_path = os.path.join(run_dir, f'{name}SED_model.png')
        comment_entry = comments.get(name, {})
        if isinstance(comment_entry, dict):
            comment = str(comment_entry.get('comment', ''))
        else:
            comment = str(comment_entry)
        reviewed = len(comment.strip()) > 0

        rows.append({
            'name': name,
            'lyric_path': lyric_path,
            'summary_path': summary_path,
            'image_fit_path': image_fit_path,
            'sed_model_path': sed_model_path,
            'has_lyric': os.path.exists(lyric_path),
            'finished': os.path.exists(summary_path),
            'reviewed': reviewed,
            'has_image': os.path.exists(image_fit_path),
            'has_sed_model': os.path.exists(sed_model_path),
            'comment': comment,
        })
    return rows

@app.route('/')
def index():
    return send_file('index.html')


@app.route('/image-previewer')
def image_previewer_page():
    return send_file('image_previewer.html')


@app.route('/job-monitor')
def job_monitor_page():
    return send_file('job_monitor.html')


@app.route('/model-editor')
def model_editor_page():
    return send_file('model_editor.html')


@app.route('/src/<path:filename>')
def source_files(filename):
    return send_from_directory('src', filename)

@app.route('/load_image', methods=['POST'])
def load_image():
    try:
        # Get parameters
        ra = float(request.form['ra'])
        dec = float(request.form['dec'])
        layer = int(request.form.get('layer', 0))
        cut_radius = int(request.form.get('cut_radius', 1000))
        
        # Check if file is uploaded or path is provided
        if 'file' in request.files and request.files['file'].filename:
            # Handle uploaded file
            file = request.files['file']
            temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.fits")
            file.save(temp_path)
            file_path = temp_path
            is_temp_file = True
        elif 'file_path' in request.form:
            # Handle server file path
            file_path = request.form['file_path']
            is_temp_file = False
            
            # Validate that the file exists
            if not os.path.exists(file_path):
                return jsonify({'error': f'File not found: {file_path}'}), 400
                
            # Security check: ensure the path is within allowed directories
            # You can modify this to restrict access to specific directories
            file_path = os.path.abspath(file_path)
            if not _is_allowed_path(file_path):
                return jsonify({'error': 'Access denied: file must be in allowed directory'}), 403
        else:
            return jsonify({'error': 'No file or file path provided'}), 400
        
        try:
            # Process the image
            hdu = fits.open(file_path)
            img = IM.image(file_path, hdu=layer, unit='cR')
            imcut, cp = img.img_cut(ra, dec, cut_radius)
            header = hdu[layer].header
            
            # Calculate statistics for display
            sky_mean, sky_median, sky_std = sigma_clipped_stats(imcut, sigma=3.0, maxiters=5)
            sky_median = 0.0
            immin = 5 * sky_std
            immax = 100 * sky_std
            
            # Generate unique ID for this image session
            image_id = str(uuid.uuid4())
            
            # Store image data
            image_store[image_id] = {
                'img': img,
                'imcut': imcut,
                'cp': cp,
                'header': header,
                'ra': ra,
                'dec': dec,
                'cut_radius': cut_radius,
                'immin': immin,
                'immax': immax,
                'sky_std': sky_std,
                'sky_median': sky_median,
                'file_path': file_path,
                'is_temp_file': is_temp_file
            }
            
            return jsonify({
                'success': True,
                'image_id': image_id,
                'image_shape': imcut.shape  # [ny, nx]
            })
            
        except Exception as e:
            # Clean up temporary file on error
            if is_temp_file and os.path.exists(file_path):
                os.remove(file_path)
            raise e
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get_image/<image_id>')
def get_image(image_id):
    try:
        if image_id not in image_store:
            return jsonify({'error': 'Image not found'}), 404
            
        data = image_store[image_id]
        imcut = data['imcut']
        immin = data['immin']
        immax = data['immax']
        sky_median = data['sky_median']
        
        # Get image dimensions
        ny, nx = imcut.shape
        
        # Create figure with exact aspect ratio of the image
        # Calculate figure size to maintain aspect ratio
        max_size = 10  # Maximum figure size in inches
        if nx > ny:
            fig_width = max_size
            fig_height = max_size * (ny / nx)
        else:
            fig_height = max_size
            fig_width = max_size * (nx / ny)
        
        # Create figure and axis with no padding
        fig = plt.figure(figsize=(fig_width, fig_height))
        ax = fig.add_axes([0, 0, 1, 1])  # [left, bottom, width, height] in figure coordinates
        
        # Display the image with proper normalization
        ax.imshow(gsutils.normimg(imcut, immin, immax, sky=sky_median, frac=0.4),
                  cmap='seismic', origin='lower', vmin=-1, vmax=1, interpolation='nearest',
                  extent=[0, nx, 0, ny])  # Set extent to match pixel coordinates
        
        # Remove all decorations
        ax.set_xlim(0, nx)
        ax.set_ylim(0, ny)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis('off')
        
        # Save to bytes with exact dimensions
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100, 
                   bbox_inches=None, pad_inches=0, facecolor='white')
        img_buffer.seek(0)
        plt.close(fig)
        
        return send_file(img_buffer, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get_coordinates', methods=['POST'])
def get_coordinates():
    try:
        data = request.json
        image_id = data['image_id']
        pixel_x = data['pixel_x']
        pixel_y = data['pixel_y']
        
        if image_id not in image_store:
            return jsonify({'error': 'Image not found'}), 404
            
        img_data = image_store[image_id]
        img = img_data['img']
        
        # Get mouse position coordinates
        mouse_delta_ra, mouse_delta_dec = gala.coordinates_transfer_inverse(pixel_x, pixel_y, img.coordinates_transfer_para)
        
        # Find nearest peak
        peak_px, peak_py, peak_delta_ra, peak_delta_dec = peak_finder(img, [pixel_x, pixel_y], 15, img.coordinates_transfer_para)
        
        
        return jsonify({
            'mouse_pixel_x': float(pixel_x),
            'mouse_pixel_y': float(pixel_y),
            'mouse_delta_ra': float(mouse_delta_ra),
            'mouse_delta_dec': float(mouse_delta_dec),
            'peak_pixel_x': float(peak_px),
            'peak_pixel_y': float(peak_py),
            'peak_delta_ra': float(peak_delta_ra),
            'peak_delta_dec': float(peak_delta_dec)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/cleanup/<image_id>', methods=['DELETE'])
def cleanup_image(image_id):
    try:
        if image_id in image_store:
            # Clean up temporary file only if it's a temp file
            img_data = image_store[image_id]
            if img_data.get('is_temp_file', False):
                file_path = img_data.get('file_path')
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            
            # Remove from store
            del image_store[image_id]
            
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/job_monitor/scan', methods=['POST'])
def job_monitor_scan():
    try:
        data = request.get_json(force=True)
        catalog_path = os.path.abspath(str(data.get('catalog_path', '')).strip())
        workspace_path = os.path.abspath(str(data.get('workspace_path', '')).strip())
        run_name = str(data.get('run_name', '')).strip()

        if not catalog_path or not workspace_path or not run_name:
            return jsonify({'error': 'catalog_path, workspace_path, and run_name are required.'}), 400
        if not catalog_path.endswith('.ecsv'):
            return jsonify({'error': 'Catalog must be an .ecsv file.'}), 400
        if not os.path.isfile(catalog_path):
            return jsonify({'error': f'Catalog not found: {catalog_path}'}), 400
        if not os.path.isdir(workspace_path):
            return jsonify({'error': f'Workspace not found: {workspace_path}'}), 400
        if not _is_allowed_path(catalog_path) or not _is_allowed_path(workspace_path):
            return jsonify({'error': 'Access denied: paths must be in allowed directories.'}), 403

        rows = _build_job_monitor_rows(catalog_path, workspace_path, run_name)
        unfinished = [row['name'] for row in rows if not row['finished']]
        return jsonify({
            'success': True,
            'catalog_path': catalog_path,
            'workspace_path': workspace_path,
            'run_name': run_name,
            'total_targets': len(rows),
            'unfinished_count': len(unfinished),
            'targets': rows,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/job_monitor/image', methods=['GET'])
def job_monitor_image():
    try:
        image_path = os.path.abspath(str(request.args.get('path', '')).strip())
        if not image_path:
            return jsonify({'error': 'Missing image path.'}), 400
        if not _is_allowed_path(image_path):
            return jsonify({'error': 'Access denied: path must be in allowed directories.'}), 403
        if not os.path.isfile(image_path):
            return jsonify({'error': f'Image not found: {image_path}'}), 404
        return send_file(image_path, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/job_monitor/export_unfinished', methods=['POST'])
def job_monitor_export_unfinished():
    try:
        data = request.get_json(force=True)
        catalog_path = os.path.abspath(str(data.get('catalog_path', '')).strip())
        workspace_path = os.path.abspath(str(data.get('workspace_path', '')).strip())
        run_name = str(data.get('run_name', '')).strip()

        if not catalog_path or not workspace_path or not run_name:
            return jsonify({'error': 'catalog_path, workspace_path, and run_name are required.'}), 400
        if not _is_allowed_path(catalog_path) or not _is_allowed_path(workspace_path):
            return jsonify({'error': 'Access denied: paths must be in allowed directories.'}), 403

        rows = _build_job_monitor_rows(catalog_path, workspace_path, run_name)
        unfinished = [row['name'] for row in rows if not row['finished']]

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        safe_run = run_name.strip().replace('/', '_')
        out_path = os.path.join(workspace_path, f'job_monitor_unfinished_{safe_run}_{timestamp}.json')
        payload = {
            'catalog_path': catalog_path,
            'workspace_path': workspace_path,
            'run_name': run_name,
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'unfinished_count': len(unfinished),
            'unfinished_targets': unfinished,
        }
        _write_json(out_path, payload)
        return jsonify({
            'success': True,
            'output_path': out_path,
            'unfinished_count': len(unfinished),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/job_monitor/save_comment', methods=['POST'])
def job_monitor_save_comment():
    try:
        data = request.get_json(force=True)
        workspace_path = os.path.abspath(str(data.get('workspace_path', '')).strip())
        run_name = str(data.get('run_name', '')).strip()
        target_name = str(data.get('target_name', '')).strip()
        comment = str(data.get('comment', '')).strip()

        if not workspace_path or not run_name or not target_name:
            return jsonify({'error': 'workspace_path, run_name, and target_name are required.'}), 400
        if not _is_allowed_path(workspace_path):
            return jsonify({'error': 'Access denied: workspace_path must be in allowed directories.'}), 403
        if not os.path.isdir(workspace_path):
            return jsonify({'error': f'Workspace not found: {workspace_path}'}), 400

        comments_path = _comments_file_path(workspace_path, run_name)
        comments = _load_comments(workspace_path, run_name)
        comments[target_name] = {
            'comment': comment,
            'updated_utc': datetime.now(timezone.utc).isoformat(),
        }
        _write_json(comments_path, comments)
        return jsonify({
            'success': True,
            'comments_path': comments_path,
            'target_name': target_name,
            'comment': comment,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


register_model_editor_routes(app, _is_allowed_path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6002)