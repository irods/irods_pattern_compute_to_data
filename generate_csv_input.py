#!/usr/bin/env python
import csv
import sys
f = sys.stdout
w = csv.writer(f)
for x in range(32):
    row = [0]*32
    if 8 < x < 24: row[8:24] = [1]*16
    w.writerow(row)
