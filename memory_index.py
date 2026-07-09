#!/usr/bin/env python3
import sys

from memoryos.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["rebuild", *sys.argv[1:]]))
