Implement a Claude Code plugin PreToolUse hook in this repository (cwd = docu-writer plugin root).

Files to create:
1. hooks/write_guard.py — Python 3 STANDARD LIBRARY ONLY (no third-party imports), runs as `python3 hooks/write_guard.py`.
2. hooks/hooks.json — registers it.

Contract (read it first; do NOT edit it): template/skills/template-workflow/SKILL.md, section "## 견본 보호" (role table + paragraph after it). Acceptance tests: tests/test_write_guard.py — do NOT edit the tests. Make them pass:
  uv run --python 3.13 --with pytest pytest tests/test_write_guard.py -q

Behaviour:
- Read one JSON object from stdin: {hook_event_name, cwd, tool_name, tool_input, agent_type?}.
- If agent_type is missing or does not start with "docu-writer:" -> allow (exit 0, print nothing).
- Checked tools: Write, Edit, MultiEdit (path = tool_input.file_path) and kordoc tools whose name ends with "kordoc__" + one of patch_document, fill_form, generate_document, convert_to_hwpx, extract_profile, render_document (path = tool_input.output_path). Other tools -> allow.
- Workspace dir D = <cwd>/.docu-writer. Protected samples = non-empty, non-comment lines of D/protected-paths (absolute paths; missing file = no protected samples).
- Contract files C = D/{protected-paths, approved.sha256, session.yaml}.
- Roles (part after "docu-writer:"):
  analyst: allow only if target is inside D and not in C.
  researcher: allow only if target == D/evidence.yaml.
  writer: allow unless target is a protected sample, or in C, or is D/profile.yaml or D/evidence.yaml.
  reviewer: deny everything.
  any other role: deny.
  Every role: target equal to a protected sample -> deny.
- Path canonicalization: relative paths resolve against cwd; then os.path.realpath; if the target does not exist, realpath its parent dir and join the name (realpath handles ../, symlinked dirs, /private on macOS). Also canonicalize D and the protected entries the same way. Additionally, when both target and a protected/contract file exist, treat them as equal if os.stat (st_dev, st_ino) match (hard links, case-insensitive FS).
- Missing path in tool_input for a checked tool -> deny. Malformed stdin JSON -> exit 2 with a message on stderr.
- To deny: print to stdout {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "<Korean reason naming role and path>"}} and exit 0.
- Keep functions small (<50 lines), no debug prints.

hooks.json format (Claude Code plugin hooks):
{"hooks": {"PreToolUse": [{"matcher": "Write|Edit|MultiEdit|mcp__.*kordoc__(patch_document|fill_form|generate_document|convert_to_hwpx|extract_profile|render_document)", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/write_guard.py\"", "timeout": 10}]}]}}

Only create/modify files under hooks/. Run the tests and report the result.
