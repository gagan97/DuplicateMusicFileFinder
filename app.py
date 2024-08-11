import os
import joblib
import logging
from concurrent.futures import ProcessPoolExecutor
from flask import Flask, request, jsonify, render_template
from fuzzywuzzy import fuzz
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis

# Set up logging
logging.basicConfig(filename='log.txt', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

app = Flask(__name__)

CACHE_FILE = 'file_cache.pkl'
IGNORE_EXTENSIONS = {'lrc', 'txt', 'jpeg', 'jpg'}

def list_files(directory):
    """List all files in the given directory, ignoring specified extensions."""
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.split('.')[-1].lower() not in IGNORE_EXTENSIONS:
                files.append(os.path.join(root, filename))
    logging.info(f"Listed {len(files)} files in directory: {directory}")
    return files

def get_file_metadata(file_path):
    """Get metadata for a file."""
    try:
        file_info = {
            'path': file_path,
            'name': os.path.basename(file_path),
            'size': os.path.getsize(file_path),
            'type': os.path.splitext(file_path)[1][1:].lower()
        }

        # Determine file type and use appropriate Mutagen class
        if file_info['type'] == 'mp3':
            audio = MP3(file_path)
        elif file_info['type'] == 'm4a':
            audio = MP4(file_path)
        elif file_info['type'] == 'flac':
            audio = FLAC(file_path)
        elif file_info['type'] == 'ogg':
            audio = OggVorbis(file_path)
        else:
            audio = MutagenFile(file_path)

        if audio:
            # Extract metadata based on file type
            if isinstance(audio, MP3):
                file_info.update({
                    'artist': str(audio.get('TPE1', 'Unknown')),
                    'album': str(audio.get('TALB', 'Unknown')),
                    'title': str(audio.get('TIT2', 'Unknown')),
                    'duration': int(audio.info.length)
                })
            elif isinstance(audio, MP4):
                file_info.update({
                    'artist': str(audio.get('\xa9ART', ['Unknown'])[0]),
                    'album': str(audio.get('\xa9alb', ['Unknown'])[0]),
                    'title': str(audio.get('\xa9nam', ['Unknown'])[0]),
                    'duration': int(audio.info.length)
                })
            elif isinstance(audio, (FLAC, OggVorbis)):
                file_info.update({
                    'artist': str(audio.get('artist', ['Unknown'])[0]),
                    'album': str(audio.get('album', ['Unknown'])[0]),
                    'title': str(audio.get('title', ['Unknown'])[0]),
                    'duration': int(audio.info.length)
                })
            else:
                # Fallback for other file types
                file_info.update({
                    'artist': str(audio.tags.get('artist', ['Unknown'])[0]) if audio.tags else 'Unknown',
                    'album': str(audio.tags.get('album', ['Unknown'])[0]) if audio.tags else 'Unknown',
                    'title': str(audio.tags.get('title', ['Unknown'])[0]) if audio.tags else 'Unknown',
                    'duration': int(audio.info.length) if audio.info else 0
                })
        else:
            file_info.update({
                'artist': 'Unknown',
                'album': 'Unknown',
                'title': 'Unknown',
                'duration': 0
            })

        logging.info(f"Retrieved metadata for file: {file_path}")
        return file_info

    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        return None

def find_similar_files(files, similarity_threshold=90):
    similar_files = {}
    group_id = 0

    for i, file1 in enumerate(files):
        if any(i in group for group in similar_files.values()):
            continue
        
        similar_group = [i]
        for j, file2 in enumerate(files[i+1:], start=i+1):
            if fuzz.ratio(os.path.basename(file1), os.path.basename(file2)) >= similarity_threshold:
                similar_group.append(j)
        
        if len(similar_group) > 1:
            similar_files[group_id] = similar_group
            group_id += 1

    logging.info(f"Found {len(similar_files)} groups of similar files")
    return similar_files

def cache_results(results):
    try:
        joblib.dump(results, CACHE_FILE)
        logging.info("Results cached successfully")
    except Exception as e:
        logging.error(f"Error caching results: {e}")

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            logging.info("Loading results from cache")
            return joblib.load(CACHE_FILE)
    except Exception as e:
        logging.error(f"Error loading cache: {e}")
        return None

@app.route('/')
def index():
    logging.info("Index page accessed")
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan_directory():
    data = request.json
    directory = data.get('directory')
    use_cache = data.get('use_cache', True)

    logging.info(f"Scanning directory: {directory}, use_cache: {use_cache}")

    if use_cache:
        cached_results = load_cache()
        if cached_results:
            logging.info("Returning cached results")
            return jsonify(cached_results)

    files = list_files(directory)

    with ProcessPoolExecutor() as executor:
        similar_files = executor.submit(find_similar_files, files).result()
        if similar_files is None:
            logging.error("Error processing filenames")
            return jsonify({'error': 'Error processing filenames'}), 500

    similar_files_str_keys = {str(k): v for k, v in similar_files.items()}

    file_metadata = []
    for file in files:
        metadata = get_file_metadata(file)
        if metadata:
            file_metadata.append(metadata)

    results = {
        'files': file_metadata,
        'similar_files': similar_files_str_keys
    }

    cache_results(results)
    logging.info("Scan completed successfully")
    return jsonify(results)

@app.route('/delete', methods=['POST'])
def delete_files():
    data = request.json
    files_to_delete = data.get('files', [])
    deleted_files = []
    errors = []

    logging.info(f"Attempting to delete {len(files_to_delete)} files")

    for file in files_to_delete:
        try:
            if os.path.exists(file):
                os.remove(file)
                deleted_files.append(file)
                logging.info(f"Deleted file: {file}")
            else:
                error_msg = f"File not found: {file}"
                errors.append(error_msg)
                logging.warning(error_msg)
        except Exception as e:
            error_msg = f"Error deleting file {file}: {str(e)}"
            errors.append(error_msg)
            logging.error(error_msg)

    result = {
        'status': 'success' if not errors else 'partial_success',
        'deleted_files': deleted_files,
        'errors': errors
    }
    logging.info(f"Delete operation completed. Status: {result['status']}")
    return jsonify(result)

if __name__ == '__main__':
    logging.info("Starting Flask application")
    app.run(host='0.0.0.0', port=5000, debug=True)
