#!/bin/zsh

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
