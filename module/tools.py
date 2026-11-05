import csv
from datetime import datetime, timedelta

def get_dataset(file):
    file_m15 = open(file)
    m15_reader = csv.reader(file_m15)

    m15_rows = []

    for row in m15_reader:
        m15_rows.append(row)
    del m15_rows[0]

    return m15_rows