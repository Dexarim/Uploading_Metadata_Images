import sys
import os
import json
import piexif
import subprocess
from PIL import Image
from datetime import datetime
import dateparser
import locale
from tqdm import tqdm

# Устанавливаем русскую локаль (для Windows)
try:
    locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
except locale.Error:
    pass

# Обработка аргументов
if len(sys.argv) < 2:
    print("❌ Укажите хотя бы одну папку для обработки.")
    print("Пример: python main.py \"Photos from 2021\" \"Photos from 2022\" [log_filename]")
    sys.exit(1)

# Последний аргумент — это лог, если он оканчивается на ".txt"
if sys.argv[-1].endswith(".txt"):
    log_filename = sys.argv[-1]
    FOLDERS = sys.argv[1:-1]
else:
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"log_{now}.txt"
    FOLDERS = sys.argv[1:]

SUPPORTED_VIDEO_FORMATS = [".mp4", ".mov", ".avi"]

# Открываем лог-файл
log_file = open(log_filename, "w", encoding="utf-8")

def log(msg):
    # print(msg)
    log_file.write(msg + "\n")

def convert_google_to_exif_time(google_time_str):
    # Убираем неразрывные пробелы и заменяем "г.," на пустую строку
    cleaned = google_time_str.replace('\u202f', ' ').replace(' ', ' ').replace('г.,', '').strip()

    # Заменяем сокращения месяцев на полные
    abbreviations = {
        "янв.": "января",
        "февр.": "февраля",
        "мар.": "марта",
        "апр.": "апреля",
        "мая": "мая",
        "июн.": "июня",
        "июл.": "июля",
        "авг.": "августа",
        "сент.": "сентября",
        "окт.": "октября",
        "нояб.": "ноября",
        "дек.": "декабря",
    }
    for abbr, full in abbreviations.items():
        cleaned = cleaned.replace(abbr, full)

    dt = dateparser.parse(cleaned)
    if dt is None:
        raise ValueError(f"Не удалось распарсить дату: {google_time_str}")
    return dt.strftime("%Y:%m:%d %H:%M:%S")

def deg_to_dms_rational(deg_float):
    deg = int(deg_float)
    min_float = (deg_float - deg) * 60
    minutes = int(min_float)
    sec = round((min_float - minutes) * 60 * 10000)
    return ((deg, 1), (minutes, 1), (sec, 10000))

def restore_video_metadata(video_path, out_path, metadata):
    taken_time = metadata.get("photoTakenTime", {}).get("formatted", None)
    location = metadata.get("geoData", {})
    creation_time = None
    if taken_time:
        try:
            dt = convert_google_to_exif_time(taken_time)
            creation_time = datetime.strptime(dt, "%Y:%m:%d %H:%M:%S").isoformat()
        except Exception as e:
            log(f"⚠️ Не удалось распарсить дату видео: {e}")
    latitude = location.get("latitude", 0)
    longitude = location.get("longitude", 0)

    cmd = ["ffmpeg", "-y", "-i", video_path, "-c", "copy"]

    if creation_time:
        cmd += ["-metadata", f"creation_time={creation_time}"]
    if latitude and longitude:
        cmd += ["-metadata", f"location={latitude:.6f}+{longitude:.6f}/"]

    cmd += [out_path]

    try:
        subprocess.run(cmd, check=True)
        log(f"✅ Видео обновлено: {video_path} → {out_path}")
    except subprocess.CalledProcessError as e:
        log(f"❌ Ошибка обновления видео {video_path}: {e}")

for FOLDER in FOLDERS:
    out_folder = os.path.join(FOLDER, "restored")
    os.makedirs(out_folder, exist_ok=True)

    for file in tqdm(os.listdir(FOLDER), desc=f"Обработка {FOLDER}"):
        if file.endswith(".jpg.supplemental-metadata.json") or any(file.endswith(ext + ".supplemental-metadata.json") for ext in SUPPORTED_VIDEO_FORMATS):
            json_path = os.path.join(FOLDER, file)
            base_filename = file.replace(".supplemental-metadata.json", "")
            media_path = os.path.join(FOLDER, base_filename)

            if not os.path.exists(media_path):
                log(f"❌ Пропущено, файл не найден: {base_filename}")
                continue

            with open(json_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            if base_filename.lower().endswith(".jpg"):
                try:
                    img = Image.open(media_path)
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

                    try:
                        taken_time = metadata["photoTakenTime"]["formatted"]
                        exif_time = convert_google_to_exif_time(taken_time)
                        exif_dict["0th"][piexif.ImageIFD.DateTime] = exif_time
                        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_time
                        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_time
                    except (KeyError, ValueError) as e:
                        log(f"⚠️ Не удалось прочитать дату для {base_filename}: {e}")

                    if "cameraMake" in metadata:
                        exif_dict["0th"][piexif.ImageIFD.Make] = metadata["cameraMake"]
                    if "cameraModel" in metadata:
                        exif_dict["0th"][piexif.ImageIFD.Model] = metadata["cameraModel"]

                    geo = metadata.get("geoData", {})
                    if geo.get("latitude") and geo.get("longitude"):
                        lat = geo["latitude"]
                        lon = geo["longitude"]
                        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = b'N' if lat >= 0 else b'S'
                        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = deg_to_dms_rational(abs(lat))
                        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b'E' if lon >= 0 else b'W'
                        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = deg_to_dms_rational(abs(lon))
                        if geo.get("altitude", 0) != 0:
                            exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (int(geo["altitude"] * 100), 100)

                    exif_bytes = piexif.dump(exif_dict)
                    out_path = os.path.join(out_folder,  base_filename)
                    img.save(out_path, exif=exif_bytes)
                    log(f"✅ Фото восстановлено: {base_filename} → restored_{base_filename}")

                except Exception as e:
                    log(f"❌ Ошибка при сохранении {base_filename}: {e}")

            elif any(base_filename.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS):
                out_path = os.path.join(out_folder, base_filename)
                restore_video_metadata(media_path, out_path, metadata)

log_file.close()
