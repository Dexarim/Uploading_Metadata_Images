
# Uploading Metadata to Images

This script is designed to restore metadata (such as capture date, camera information, and GPS coordinates) in image and video files downloaded via [Google Takeout](https://takeout.google.com/).

It reads ```.supplemental-metadata.json``` files, matches them with the corresponding media files, and embeds the metadata back into the media—EXIF for images and container-level metadata for videos.

Supported formats include .jpg images and video files with extensions ```.mp4```, ```.mov```, and ```.avi```.
The processed files are saved in a separate restored folder within the specified directory.


## Run Locally

Clone the project

```bash
  git clone https://github.com/Dexarim/Uploading_Metadata_to_Images.git
```

Go to the project directory

```bash
  cd Uploading_Metadata_Images
```

Install dependencies

```bash
  pip install -r requirements.txt
```

Start the server

```bash
  python main.py "path/folder"

```

```bash
  python main.py "path/folder1" "path/folder1" mylog.txt


```
## License

[MIT](https://choosealicense.com/licenses/mit/)

