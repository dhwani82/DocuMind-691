import os
from pathlib import Path

def load_config(path):
    with open(path) as f:
        return f.read()

def save_result(data, filename):
    Path(filename).write_text(data)

class DataProcessor:
    def process(self, raw):
        return raw.strip().lower()

    def validate(self, data):
        return len(data) > 0
