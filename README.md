# DuplicateMusicFileFinder
Creating a basic Flask(python) application to find similar music files on the specified path from the front end. You will get options to delete the files from the group of similar files

This is a web application that finds files with 80% or more similar names in all subfolders of a specified directory, and allows users to interactively delete duplicate files. The application will display file details including name, size, type, and metadata like Artist, Album, Title, and Duration for audio files.

To run this application:

1. Install the required packages:
     
2. Run the Flask server:
   ```
   python app.py
   ```
3. Open a web browser and go to `http://localhost:5000` or `http://ip-address-host:5000`.

This application will:
- Allow users to enter a directory path
- Find files with 80% or more similar names in all subfolders
- Display file details including metadata for audio files
- Provide an interface for users to select which files to delete
- Delete the selected files and show a confirmation page

Note: This application handles file deletion, which is a sensitive operation. Ensure you have proper security measures in place before deploying this in a production environment.
