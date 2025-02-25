import os
import math
import asyncio
import aiohttp
import time
from tqdm import tqdm

# Parameters - ADJUST THESE
min_zoom = 0
max_zoom = 15  # Higher zooms = more storage required
center_lat = 40.7128  # New York City (example)
center_lon = -74.0060
radius = 0.1  # Degrees ~ 50km
output_dir = "static/tiles"
max_concurrent_downloads = 5  # Limit concurrent connections to be nice to the server
rate_limit_delay = 0.2  # Seconds between requests

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return (xtile, ytile)

async def download_tile(session, semaphore, tile_url, output_file, pbar, counters):
    """Download a single tile asynchronously"""
    if os.path.exists(output_file):
        # Skip existing files
        counters['skipped'] += 1
        pbar.update(1)
        return
    
    async with semaphore:  # Limit concurrent downloads
        try:
            # Use a custom User-Agent and respect OSM's tile usage policy
            headers = {'User-Agent': 'Rocket-Telemetry-Offline-Map/1.0'}
            
            # Add a small delay to avoid hammering the server
            await asyncio.sleep(rate_limit_delay)
            
            async with session.get(tile_url, headers=headers) as response:
                if response.status == 200:
                    content = await response.read()
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    with open(output_file, 'wb') as out_file:
                        out_file.write(content)
                    counters['downloaded'] += 1
                else:
                    print(f"Error downloading {tile_url}: HTTP {response.status}")
                    counters['failed'] += 1
        except Exception as e:
            print(f"Error downloading {tile_url}: {e}")
            counters['failed'] += 1
        finally:
            pbar.update(1)

async def main():
    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a semaphore to limit concurrent downloads
    semaphore = asyncio.Semaphore(max_concurrent_downloads)
    
    # Create a list to store all download tasks
    all_tasks = []
    total_tiles = 0
    
    # Counter dictionary to track statistics
    counters = {
        'downloaded': 0,
        'skipped': 0,
        'failed': 0
    }
    
    # First pass: count total tiles and create directory structure
    for zoom in range(min_zoom, max_zoom + 1):
        zoom_dir = os.path.join(output_dir, str(zoom))
        os.makedirs(zoom_dir, exist_ok=True)
        
        # Calculate bounds
        min_lat, max_lat = center_lat - radius, center_lat + radius
        min_lon, max_lon = center_lon - radius, center_lon + radius
        
        # Convert bounds to tile coordinates
        min_x, max_y = deg2num(min_lat, min_lon, zoom)
        max_x, min_y = deg2num(max_lat, max_lon, zoom)
        
        for x in range(min_x, max_x + 1):
            x_dir = os.path.join(zoom_dir, str(x))
            os.makedirs(x_dir, exist_ok=True)
            
            for y in range(min_y, max_y + 1):
                total_tiles += 1
    
    print(f"Preparing to download {total_tiles} tiles...")
    
    # Create a progress bar
    pbar = tqdm(total=total_tiles, desc="Downloading tiles")
    
    # Second pass: download tiles
    async with aiohttp.ClientSession() as session:
        for zoom in range(min_zoom, max_zoom + 1):
            zoom_dir = os.path.join(output_dir, str(zoom))
            
            # Calculate bounds
            min_lat, max_lat = center_lat - radius, center_lat + radius
            min_lon, max_lon = center_lon - radius, center_lon + radius
            
            # Convert bounds to tile coordinates
            min_x, max_y = deg2num(min_lat, min_lon, zoom)
            max_x, min_y = deg2num(max_lat, max_lon, zoom)
            
            for x in range(min_x, max_x + 1):
                x_dir = os.path.join(zoom_dir, str(x))
                
                for y in range(min_y, max_y + 1):
                    tile_url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                    output_file = os.path.join(x_dir, f"{y}.png")
                    
                    # Create and add the download task
                    task = asyncio.create_task(
                        download_tile(session, semaphore, tile_url, output_file, pbar, counters)
                    )
                    all_tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*all_tasks)
    
    pbar.close()
    
    # Print summary statistics
    print("\nDownload Summary:")
    print(f"  Total tiles processed: {total_tiles}")
    print(f"  Downloaded: {counters['downloaded']}")
    print(f"  Skipped (already exist): {counters['skipped']}")
    print(f"  Failed: {counters['failed']}")
    
    if counters['failed'] == 0:
        print("\nAll tiles processed successfully!")
    else:
        print(f"\nCompleted with {counters['failed']} failed downloads.")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())