#!/usr/bin/env python3
import sys

from memoryos.cli import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--project"] and len(args) >= 2:
        args = [args[1], *args[2:]]
    raise SystemExit(main(["context", *args]))
