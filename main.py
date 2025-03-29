import os
import json
import shutil
from pathlib import Path
import re
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import piexif
from datetime import datetime

def normalize_filename(name):
    """Removes (x) numbering and -edited suffix from filenames to enable better matching."""
    # Remove (x) numbering
    name = re.sub(r"\(\d+\)", "", name)
    # Remove -edited suffix
    name = re.sub(r"-edited$", "", name)
    # Remove _p suffix
    name = re.sub(r"_p$", "", name)
    # Remove spaces and dots from date format
    name = re.sub(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})", r"\1\2\3_\4\5\6", name)
    # Remove any remaining spaces
    name = re.sub(r"\s+", "", name)
    # Remove any remaining dots
    name = re.sub(r"\.", "", name)
    # Remove any remaining underscores at the end
    name = re.sub(r"_+$", "", name)
    return name

def find_json_for_photo(photo_path, json_files):
    """Finds the corresponding JSON file for a given photo, handling variations in file extensions and numbering."""
    base_name = photo_path.stem  # Original filename without extension
    normalized_base = normalize_filename(base_name)

    # First attempt: exact match
    for json_file in json_files:
        if json_file.stem.startswith(base_name):
            return json_file

    # Second attempt: try matching after normalizing
    for json_file in json_files:
        json_base = normalize_filename(json_file.stem)
        if json_base == normalized_base:
            return json_file

    # Third attempt: try matching without the (1) suffix
    base_without_number = re.sub(r"\(\d+\)$", "", normalized_base)
    for json_file in json_files:
        json_base = normalize_filename(json_file.stem)
        json_without_number = re.sub(r"\(\d+\)$", "", json_base)
        if json_without_number == base_without_number:
            return json_file

    # Fourth attempt: try matching the base date-time pattern
    date_pattern = re.search(r"(\d{8}_\d{6})", normalized_base)
    if date_pattern:
        date_str = date_pattern.group(1)
        for json_file in json_files:
            json_base = normalize_filename(json_file.stem)
            if date_str in json_base:
                return json_file

    # Fifth attempt: try matching without any numbering or suffixes
    base_clean = re.sub(r"\(\d+\)|-\w+$|_\w+$", "", normalized_base)
    for json_file in json_files:
        json_base = normalize_filename(json_file.stem)
        json_clean = re.sub(r"\(\d+\)|-\w+$|_\w+$", "", json_base)
        if json_clean == base_clean:
            return json_file

    return None  # Return None if no match is found

def get_exif_gps_dict(lat, lon):
    """Convert latitude and longitude to EXIF GPS format."""
    def convert_to_degrees(value):
        d = float(value)
        degrees = int(d)
        minutes = int((d - degrees) * 60)
        seconds = int(((d - degrees) * 60 - minutes) * 60)
        return ((degrees, 1), (minutes, 1), (seconds, 1))

    lat_deg = convert_to_degrees(abs(lat))
    lon_deg = convert_to_degrees(abs(lon))
    
    lat_ref = 'N' if lat >= 0 else 'S'
    lon_ref = 'E' if lon >= 0 else 'W'
    
    gps_dict = {
        "GPSLatitude": lat_deg,
        "GPSLatitudeRef": lat_ref,
        "GPSLongitude": lon_deg,
        "GPSLongitudeRef": lon_ref,
        "GPSVersionID": (2, 2, 0, 0),
        "GPSAltitudeRef": 0,
        "GPSAltitude": (0, 1),
        "GPSTimeStamp": ((0, 1), (0, 1), (0, 1)),
        "GPSSatellites": "",
        "GPSStatus": "A",
        "GPSMeasureMode": "3",
        "GPSDOP": (0, 1),
        "GPSSpeedRef": "K",
        "GPSSpeed": (0, 1),
        "GPSTrackRef": "T",
        "GPSTrack": (0, 1),
        "GPSImgDirectionRef": "M",
        "GPSImgDirection": (0, 1),
        "GPSMapDatum": "WGS-84",
        "GPSDestLatitudeRef": "N",
        "GPSDestLatitude": ((0, 1), (0, 1), (0, 1)),
        "GPSDestLongitudeRef": "E",
        "GPSDestLongitude": ((0, 1), (0, 1), (0, 1)),
        "GPSDestBearingRef": "M",
        "GPSDestBearing": (0, 1),
        "GPSDestDistanceRef": "K",
        "GPSDestDistance": (0, 1),
        "GPSProcessingMethod": "",
        "GPSAreaInformation": "",
        "GPSDateStamp": "",
        "GPSDifferential": 0
    }
    return gps_dict

def process_photos_and_json(photo_dir, json_dir, output_dir):
    """Merges photos and videos with their metadata JSON files."""
    photo_dir = Path(photo_dir)
    json_dir = Path(json_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_extensions = ["*.jpg", "*.png", "*.gif", "*.heic", "*.mp4", "*.mov", "*.bmp"]
    media_files = []
    for ext in file_extensions:
        media_files.extend(photo_dir.glob(ext))
    
    # Get JSON files from both source and output directories
    json_files = []
    for json_path in list(json_dir.glob("*.json")) + list(output_dir.glob("*.json")):
        if json_path.exists():  # Only add files that actually exist
            json_files.append(json_path)
    
    for media in media_files:
        try:
            json_file = find_json_for_photo(media, json_files)
            if json_file and json_file.exists():  # Double check the file exists
                with open(json_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Get timestamp and GPS coordinates
                photo_taken_time = metadata.get("photoTakenTime", {})
                timestamp = photo_taken_time.get("timestamp")
                formatted_time = photo_taken_time.get("formatted", "")
                
                # Convert timestamp to datetime for file creation time
                if timestamp:
                    try:
                        # Ensure timestamp is a string and convert to integer
                        timestamp_str = str(timestamp)
                        timestamp_int = int(timestamp_str)
                        # Convert Unix timestamp to datetime
                        photo_date = datetime.fromtimestamp(timestamp_int)
                        # Format for file creation time
                        creation_time = photo_date.strftime("%Y:%m:%d %H:%M:%S")
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Could not convert timestamp for {media.name}: {str(e)}")
                        creation_time = formatted_time
                else:
                    creation_time = formatted_time
                
                geo_data = metadata.get("geoData", {})
                latitude = geo_data.get("latitude", 0)
                longitude = geo_data.get("longitude", 0)
                altitude = geo_data.get("altitude", 0)
                
                # Get people tags
                people = metadata.get("people", [])
                people_names = [person.get("name", "") for person in people]
                
                if timestamp:
                    new_name = f"{timestamp}_{media.name}"
                    new_media_path = output_dir / new_name
                    
                    # Copy the file first
                    shutil.copy(media, new_media_path)
                    
                    # If it's a JPEG, add GPS data to EXIF
                    if media.suffix.lower() in ['.jpg', '.jpeg']:
                        try:
                            # Create EXIF data with GPS information
                            exif_dict = {
                                "GPS": get_exif_gps_dict(latitude, longitude),
                                "Exif": {
                                    "DateTimeOriginal": formatted_time,
                                    "DateTimeDigitized": formatted_time,
                                    "DateTime": formatted_time,
                                },
                                "0th": {
                                    "DateTime": formatted_time,
                                    "DateTimeOriginal": formatted_time,
                                    "DateTimeDigitized": formatted_time,
                                }
                            }
                            exif_bytes = piexif.dump(exif_dict)
                            
                            # Insert EXIF data into the image
                            piexif.insert(exif_bytes, str(new_media_path))
                            
                            # Set file creation time to photo taken time
                            try:
                                os.utime(new_media_path, (timestamp_int, timestamp_int))
                            except Exception as e:
                                print(f"Warning: Could not set file time for {media.name}: {str(e)}")
                        except Exception as e:
                            print(f"Warning: Could not add EXIF data to {media.name}: {str(e)}")
                    
                    # Copy JSON file
                    shutil.copy(json_file, output_dir / f"{new_name}.json")
                    
                    # Delete original files after successful processing
                    os.remove(media)
                    if json_file.parent == photo_dir:  # Only delete if it's in the source directory
                        os.remove(json_file)
                    
                    print(f"Processed and deleted: {media.name} -> {new_name}")
                    if people_names:
                        print(f"People in photo: {', '.join(people_names)}")
                else:
                    print(f"Skipping {media.name}, missing timestamp metadata.")
            else:
                print(f"No JSON metadata found for {media.name}")
        except Exception as e:
            print(f"Error processing {media.name}: {str(e)}")

# Example Usage
process_photos_and_json("Photos from 2015", "Photos from 2015", "output")
