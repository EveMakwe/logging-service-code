#!/usr/bin/env python3

import sys
import re


def emoji_plan_line(line):
    # Only replace markers at the start of the line (standard for terraform plans)
    line = re.sub(r'^(\s*)\+', r'\1🌱 +', line)   # create
    line = re.sub(r'^(\s*)-', r'\1🗑️ -', line)   # destroy
    line = re.sub(r'^(\s*)~', r'\1🔄 ~', line)   # change
    return line


if __name__ == "__main__":
    for line in sys.stdin:
        print(emoji_plan_line(line.rstrip()))
