#!/usr/bin/env python3
"""Backfill monitoring metadata on a candidate list or state file."""

import argparse
import json
from pathlib import Path

from metadata import annotate_record, explicitly_older_than_target


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    parser.add_argument("--state", action="store_true", help="Annotate state.postings instead of a list")
    parser.add_argument("--drop-out-of-scope", action="store_true", help="Drop records whose primary content only names an older cohort")
    args = parser.parse_args()

    value = load(args.input)
    config = load(args.config)
    if args.state:
        postings = value.get("postings", {})
        if args.drop_out_of_scope:
            postings = {
                key: record for key, record in postings.items()
                if not explicitly_older_than_target(record, config)
            }
            value["postings"] = postings
        for record in postings.values():
            annotate_record(record, config)
    else:
        if args.drop_out_of_scope:
            value = [record for record in value if not explicitly_older_than_target(record, config)]
        for record in value:
            annotate_record(record, config)
    output = args.output or args.input
    save(output, value)
    print(json.dumps({"output": str(Path(output)), "records": len(value.get("postings", {})) if args.state else len(value)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
