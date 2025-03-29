import os
import shutil
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import pathlib
import re
import json

def get_date_from_filename(filename):
    # Look for date pattern YYYYMMDD in filename
    date_pattern = r'(\d{8})'
    match = re.search(date_pattern, filename)
    if match:
        date_str = match.group(1)
        try:
            date = datetime.strptime(date_str, '%Y%m%d')
            # Validate the date is reasonable (between 1900 and current year)
            if 1900 <= date.year <= datetime.now().year:
                return date
        except ValueError:
            return None
    return None

def get_date_from_json(image_path):
    # Try to find and read the corresponding JSON file
    # Try different possible JSON file extensions
    possible_json_extensions = [
        image_path.with_suffix('.jpg.json'),
        image_path.with_suffix('.jpeg.json'),
        image_path.with_suffix('.png.json'),
        image_path.with_suffix('.gif.json'),
        image_path.with_suffix('.mp4.json'),
        image_path.with_suffix('.bmp.json'),  # Added BMP
        image_path.with_suffix('.json')
    ]
    
    # Also try looking for JSON with the original filename (without timestamp)
    original_name = re.sub(r'^\d+_', '', image_path.name)  # Remove timestamp prefix if present
    original_path = image_path.with_name(original_name)
    possible_json_extensions.extend([
        original_path.with_suffix('.json'),
        original_path.with_suffix('.bmp.json')  # For BMP files
    ])
    
    for json_path in possible_json_extensions:
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    photo_taken_time = metadata.get("photoTakenTime", {})
                    timestamp = photo_taken_time.get("timestamp")
                    if timestamp:
                        date = datetime.fromtimestamp(int(timestamp))
                        # Validate the date is reasonable (between 1900 and current year)
                        if 1900 <= date.year <= datetime.now().year:
                            return date
            except Exception as e:
                print(f"Error reading JSON data from {json_path}: {e}")
    return None

def get_date_taken(image_path):
    # First try to get date from EXIF data (only for formats that support EXIF)
    try:
        image = Image.open(image_path)
        # Only try to get EXIF data for formats that support it (JPEG)
        if image.format in ['JPEG', 'TIFF']:
            exif = image._getexif()
            if exif is not None:
                for tag_id in exif:
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'DateTimeOriginal':
                        date = datetime.strptime(exif[tag_id], '%Y:%m:%d %H:%M:%S')
                        # Validate the date is reasonable (between 1900 and current year)
                        if 1900 <= date.year <= datetime.now().year:
                            return date
    except Exception as e:
        print(f"Error reading EXIF data from {image_path}: {e}")
    
    # If EXIF data is not available or invalid, try to get date from JSON
    json_date = get_date_from_json(image_path)
    if json_date:
        return json_date
    
    # If JSON date is not available, try to get date from filename
    return get_date_from_filename(image_path.name)

def create_date_folders():
    # Get the output directory path
    output_dir = pathlib.Path("output")
    
    # Check if output directory exists
    if not output_dir.exists():
        print("Output directory not found!")
        return
    
    # Define supported file extensions (images and videos)
    supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.mp4'}
    
    # Process each file in the output directory
    for file_path in output_dir.glob("*"):
        if file_path.is_file():
            # Skip JSON files and unsupported files
            if file_path.suffix.lower() == '.json' or file_path.suffix.lower() not in supported_extensions:
                continue
                
            # Get the date taken from the file
            date_taken = get_date_taken(file_path)
            
            if date_taken:
                # Create year and month folders
                year_folder = output_dir / str(date_taken.year)
                month_folder = year_folder / f"{date_taken.month:02d}"
                
                # Create folders if they don't exist
                year_folder.mkdir(exist_ok=True)
                month_folder.mkdir(exist_ok=True)
                
                # Move the file to the month folder
                try:
                    shutil.move(str(file_path), str(month_folder / file_path.name))
                    print(f"Moved {file_path.name} to {month_folder}")
                except Exception as e:
                    print(f"Error moving {file_path.name}: {e}")
            else:
                print(f"Could not get date taken for {file_path.name}")

if __name__ == "__main__":
    create_date_folders()
