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

        if "delete" in action:
            errors.append(
                f"Resource '{address}' is being destroyed."
            )
            continue
        if "create" in action:
            continue
        if action == ["no-op"]:
            continue

        if "update" in action or "modify" in action:
            before = rc.get('change', {}).get('before', {})
            after = rc.get('change', {}).get('after', {})
            before_tags = before.get('tags') or {}
            after_tags = after.get('tags') or {}

            changed_keys = set(before_tags.keys()) | set(after_tags.keys())
            changed_keys = {
                k for k in changed_keys
                if before_tags.get(k) != after_tags.get(k)
            }
            other_changed_keys = changed_keys - {"GitCommitHash"}

            all_changes = set()
            if before and after:
                for key in set(before.keys()) | set(after.keys()):
                    if (
                        before.get(key) != after.get(key)
                        and key != "tags"
                    ):
                        all_changes.add(key)

            if all_changes:
                msg = (
                    f"Resource '{address}' is being modified: "
                    "attributes changed (not tags): "
                    f"{sorted(all_changes)}"
                )
                errors.append(msg)
            elif other_changed_keys:
                msg = (
                    f"Resource '{address}' is being modified: tags other than "
                    "'GitCommitHash' are changed: "
                    f"{sorted(other_changed_keys)}"
                )
                errors.append(msg)
        else:
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
                "✅ Safe to apply: Only creates or only allowed tag "
                "modifications detected."
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
