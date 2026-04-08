# Daily Standup Automation

Minimal implementation for a Codex-based standup workflow with:

- `2` automation prompts: morning and afternoon
- JSON config for schedule-related settings
- JSON state per workday
- Python scripts to update state and render the final report

## Files

- `standup.config.json`: shared config for timezone, expected hours, and workdays
- `schema/workday-state.schema.json`: reference JSON schema for each workday state file
- `scripts/update_state.py`: merge morning or afternoon extracted data into the state JSON
- `scripts/render_report.py`: render the final `Yesterday/Today` report with optional blocker/time segments and optionally write it back
- `prompts/morning_prompt.md`: prompt template for the morning automation
- `prompts/afternoon_prompt.md`: prompt template for the afternoon automation
- `docs/daily-standup/`: generated JSON state files

## Example usage

Morning:

```bash
python3 scripts/update_state.py \
  --stage morning \
  --workday 2026-04-07 \
  --payload-file examples/morning_payload.json
```

Afternoon:

```bash
python3 scripts/update_state.py \
  --stage afternoon \
  --workday 2026-04-07 \
  --payload-file examples/afternoon_payload.json
python3 scripts/render_report.py --workday 2026-04-07 --write-back
```

## Automation setup

Use the prompt templates in `prompts/` when creating your Codex automations. The morning automation should read the previous workday report first and treat yesterday's `Today` section as the draft baseline for today's plan. The actual schedule should be configured in Codex automation itself, while `standup.config.json` stays in sync with the intended morning and afternoon times.

