#!/usr/bin/env python3

import json
import sys
import glob


def check_plan(plan):
    changes = plan.get('resource_changes', [])
    errors = []
    for rc in changes:
        action = rc.get('change', {}).get('actions', [])
        address = rc.get('address')
        if not action:
            continue

        # Replacement: delete+create (will be replaced)
        if "delete" in action and "create" in action:
            errors.append(
                f"Resource '{address}' will be replaced (delete and create)."
            )
            continue

        # Destroy
        if action == ["delete"]:
            errors.append(
                f"Resource '{address}' is being destroyed."
            )
            continue

        # In-place update (safe): do NOT warn
        if action == ["update"]:
            continue

        # Creation only (safe): do NOT warn
        if action == ["create"]:
            continue

        # No-op (safe)
        if action == ["no-op"]:
            continue

        # Unknown/unsupported action
        errors.append(
            f"Resource '{address}' has unsupported action: {action}"
        )
    return errors


def main():
    plan_files = sys.argv[1:] if len(sys.argv) > 1 else glob.glob("*.tfplan.json")

    if not plan_files:
        print(
            "No .tfplan.json files found. "
            "Usage: python check_plan.py [tfplan.json ...]"
        )
        sys.exit(1)

    has_error = False

    for fname in plan_files:
        print(f"Checking plan file: {fname}")
        try:
            with open(fname) as f:
                plan = json.load(f)
        except Exception as e:
            print(f"ERROR: Cannot read or parse {fname}: {e}")
            has_error = True
            continue

        errors = check_plan(plan)
        if not errors:
            print(
                "✅ Safe to apply: Only creates or in-place updates detected."
            )
        else:
            print("❌ Do NOT apply:")
            for err in errors:
                print("  -", err)
            has_error = True
        print("-" * 60)

    # Uncomment the next line to make CI fail on unsafe plans:
    # if has_error:
    #     sys.exit(2)


if __name__ == "__main__":
    main()
