import numpy as np
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
from astropy.stats import sigma_clipped_stats
from reproject import reproject_exact, reproject_adaptive
import jax.numpy as jnp

def peak_finder(img, posi, size, transpar=None):
    """
    Find peaks in the image near [posi[0], posi[1]] with a given square size.
    
    Parameters:
    -----------
    img : IM.image object
        The image object with data and coordinate transformation
    posi : list
        [x, y] position in pixels
    size : int
        Half-size of the search region
    transpar : optional
        Coordinate transformation parameters
    
    Returns:
    --------
    px, py : float
        Peak position in pixels
    sx, sy : float (if transpar provided)
        Peak position in sky coordinates
    """
    # Get the image data
    if hasattr(img, 'data'):
        image_data = img.data
    elif hasattr(img, 'img'):
        image_data = img.img
    else:
        # Assume img is the image array itself
        image_data = img
    
    # Get the size of the image
    ny, nx = image_data.shape
    
    # Ensure position is within bounds
    x_center = max(size, min(nx - size - 1, posi[0]))
    y_center = max(size, min(ny - size - 1, posi[1]))
    
    # Define search region bounds
    x_min = max(0, x_center - size)
    x_max = min(nx, x_center + size + 1)
    y_min = max(0, y_center - size)
    y_max = min(ny, y_center + size + 1)
    
    # Extract the search region
    search_region = image_data[y_min:y_max, x_min:x_max]
    
    # Find the peak in the search region
    peak_idx = np.unravel_index(np.argmax(search_region), search_region.shape)
    
    # Convert back to full image coordinates
    py = y_min + peak_idx[0]
    px = x_min + peak_idx[1]
    
    if transpar is None:
        return px, py
    else:
        sx, sy = gala.coordinates_transfer_inverse(px, py, transpar)
        return px, py, sx, sy

# Legacy function for backward compatibility
def process_image_interactive(fname, ra, dec, layer=0, cutr=1000):
    """
    Process image for interactive display (legacy function)
    """
    hdu = fits.open(fname)
    img = IM.image(fname, hdu=layer, unit='cR')
    imcut, cp = img.img_cut(ra, dec, cutr)
    header = hdu[layer].header

    # Calculate display parameters
    sky_mean, sky_median, sky_std = sigma_clipped_stats(imcut, sigma=3.0, maxiters=5)
    sky_median = 0.0
    immin = 5 * sky_std
    immax = 100 * sky_std
    
    return img, imcut, cp, header, immin, immax

if __name__ == "__main__":
    # Example usage for testing
    print("Image preview module loaded successfully")
    print("Available functions:")
    print("- peak_finder(img, posi, size, transpar=None)")
    print("- process_image_interactive(fname, ra, dec, layer=0, cutr=1000)")


