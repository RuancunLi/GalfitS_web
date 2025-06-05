from flask import Flask, request, jsonify, send_file, render_template
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
from image_preview import peak_finder

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Store image data in memory (in production, use a proper database)
image_store = {}

@app.route('/')
def index():
    return send_file('index.html')

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
            if not file_path.startswith('/home/liruancun/'):
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6002)