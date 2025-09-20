#!/bin/zsh
# Ensure ../data/raw exists
RAW_DIR="../data/raw"
if [ ! -d "$RAW_DIR" ]; then
    mkdir -p "$RAW_DIR"
fi

# Only download if data/raw is empty
if [ -z "$(ls -A $RAW_DIR)" ]; then
    ZIP_PATH="../data/raw/raw_data.zip"
    GDRIVE_ID="1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH" # Oracle Elixir's game data folder
    echo "Downloading data/raw from Google Drive..."
    gdown --folder "https://drive.google.com/drive/u/1/folders/$GDRIVE_ID" -O "$RAW_DIR"

    # If any zip files were downloaded, unzip them into data/raw. Probably unnecessary bc gdown downloads every file separately.
    for zipfile in "$RAW_DIR"/*.zip; do
        if [ -f "$zipfile" ]; then
            echo "Unzipping $zipfile into $RAW_DIR"
            unzip -o "$zipfile" -d "$RAW_DIR"
            rm "$zipfile"
        fi
    done
else
    echo "$RAW_DIR is not empty. Skipping download."
fi

# Delete the database if it exists
DB_PATH="../db/prometheus.db"
if [ -f "$DB_PATH" ]; then
    rm "$DB_PATH"
fi

# Create an empty database file
touch "$DB_PATH"

# Run all scripts that begin with a number in the current directory
for script in ./[0-9]*; do
    if [[ "$script" == *.sql ]]; then
        echo "Running SQL script: $script"
        sqlite3 "$DB_PATH" < "$script"
    elif [[ "$script" == *.py ]]; then
        echo "Running Python script: $script"
        python3 "$script"
    fi
done
