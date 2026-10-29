# Canvas event management

Use these tools to export Canvas calendar events, create new events from a CSV, update existing events from a CSV or Excel file, or delete all calendar events in selected courses.

## Which file do I need?

| Task | Command | File you provide | Required data |
| --- | --- | --- | --- |
| Export events from Canvas | `export` | `course_ids.csv` | A `course_id` column with one Canvas course ID per row. |
| Import **new** events | `import` | `import-events.csv` | `Course ID`, `Title`, `Start Date`; optional details and section schedules. |
| Modify existing events | `update` | `update-events.csv` or `.xlsx` | `item_id` (or `event_id`) plus the columns you want to change. |
| Delete course events | `delete` | `course_ids.csv` | A `course_id` column. Deletes all calendar events returned for those courses. |

Use **`import` to add new events** and **`update` to modify existing events**. The two operations use different column names and date formats.

The filenames above are suggested names. You can use other names by passing their paths in the command. Examples below place all data files in the repository root, beside this README. They do not create or move those files for you.

## 1. Setup and file rules

Open a PowerShell terminal in this repository and install the requirements (Python 3.10+):

```powershell
python -m pip install -r requirements.txt
$env:CANVAS_URL = "https://school.instructure.com"
```

Replace the URL with your Canvas instance. Commands ask for the API token privately. If the URL is not set, they ask for that too. You can alternatively supply `CANVAS_API_TOKEN` in the environment or override the URL with `--url`. Do not put credentials in data files.

For every input file:

- Put column names in the first row and one record per following row.
- Save CSV files as **CSV UTF-8 (comma-delimited)**. Do not use tabs or semicolons as separators.
- Use actual Canvas numeric IDs, not course codes, event titles, or section labels such as `L01`. Sample IDs below are placeholders.
- In CSV text containing commas, wrap the cell in double quotes. Inside a quoted cell, represent a literal double quote as two double quotes. Excel's CSV save handles this.
- Paths are relative to the terminal's current directory. For a file in a subfolder, pass that path explicitly, for example `--courses canvas_events/course_ids.csv`.
- When a default input is used, commands check the current directory first, then `canvas_events/`: `course_ids.csv` for export/delete, `import-events.csv` for import, and `export-events.csv` for update. Explicit input paths are used exactly as supplied. Export output defaults to the current directory.

### Start with the supplied templates

The files in `examples/` contain fictional IDs and data. Copy a template, replace its IDs and values with your own, and keep your working copy outside `examples/`.

| Template | Use |
| --- | --- |
| `examples/course_ids.csv` | Course list for export or delete. |
| `examples/import-events.csv` | New course-wide events. |
| `examples/import-section-events.csv` | New events with section schedules. |
| `examples/update-events.csv` | Existing event edits, including an explicit description clear. |

For example:

```powershell
Copy-Item examples/import-events.csv import-events.csv
```

Edit the copied file, then preview it with `python -m canvas_events import`. The same approach works for course lists and update files; pass `update-events.csv` explicitly to update because its default input is `export-events.csv`.

## 2. Export events: course list in, event spreadsheet out

**Prepare `course_ids.csv`:**

```csv
course_id
12345
67890
```

The header must be `course_id`. Each nonblank ID must be a positive whole number. Duplicate IDs are read only once.

**Run:**

```powershell
python -m canvas_events export --courses course_ids.csv
```

**Result:** `export-events.csv`, with one row per calendar event, including individual section events. Hidden section parent containers are omitted. The output columns are:

```text
item_id,course_id,course_name,source,title,start_at,end_at,due_at,context_code,description,location_name,all_day,created_at,updated_at,workflow_state,assignment_type,html_url
```

You can edit this file and use it as update input without renaming or removing columns. Save an edited copy as `update-events.csv` to retain the original export.

Export options:

| Option | Meaning |
| --- | --- |
| `--include-assignments` | Also export assignments with due dates for reference. Without this flag, export includes calendar events only. The updater skips assignment rows. |
| `--time-zone America/Vancouver` | Timezone used to display exported times; this is the default. Other IANA timezone names are accepted. |
| `--output filename.csv` | Destination CSV. An existing destination is replaced after a complete successful export. |

The default export filename is **`export-events.csv`** in the current directory. Use `--output filename.csv` to choose another name. With no `--courses`, export looks for `course_ids.csv` in the current directory, then in `canvas_events/`.

## 3. Import new events: use `import-events.csv`

Use **CSV only**, with these exact column names:

| Column | Required? | Format / meaning |
| --- | --- | --- |
| `Course ID` | Yes | Canvas course ID, e.g. `12345`. |
| `Title` | Yes | Event title. |
| `Start Date` | Yes | `MM/DD/YYYY HH:MM`, e.g. `11/02/2026 09:00`. |
| `End Date` | No | Same format. Blank uses the start time. Must not precede the start. |
| `Description` | No | Plain text or HTML. |
| `All Day` | No | `true`, `1`, `yes`, or `y` means true, ignoring case. Blank and other values mean false. |
| `Location` | No | Location name. |

All creation dates are **Vancouver local time (`America/Vancouver`)**, using a 24-hour clock. Do not add `Z` or a UTC offset in this file.

**Example `import-events.csv`:**

```csv
Course ID,Title,Start Date,End Date,Description,All Day,Location
12345,Orientation,11/02/2026 09:00,11/02/2026 10:00,Welcome session,false,Room 101
12345,Independent study,11/03/2026 00:00,11/03/2026 23:59,Reading day,true,
```

**Preview, then import:**

```powershell
python -m canvas_events import import-events.csv
python -m canvas_events import import-events.csv --apply
```

With no file argument, import first checks `import-events.csv` in the terminal's current directory, then `canvas_events/import-events.csv` beside the implementation files. An explicit path is used exactly as supplied. For example, from the repository root you can run `python -m canvas_events import canvas_events/import-events.csv`. Preview validates locally without contacting Canvas. Every applied row creates a new event; applying the same file again can create duplicates.

### Creating section schedules

Keep the required course-level columns above. Add these three columns for each section schedule you need:

| Section slot | Columns |
| --- | --- |
| L01 | `L01 Start Date`, `L01 End Date`, `L01 Section ID` |
| L02 through L06 | The same three names with `L02`, `L03`, `L04`, `L05`, or `L06` as the prefix. |

A section schedule is included only when both its start and section ID are filled in. Blank section end uses that section's start. Dates use the same Vancouver local format. The ID is the numeric **Canvas section ID**; the prefix labels the CSV slot.

```csv
Course ID,Title,Start Date,End Date,L01 Start Date,L01 End Date,L01 Section ID,L02 Start Date,L02 End Date,L02 Section ID
12345,Lab,11/02/2026 09:00,11/02/2026 12:00,11/02/2026 09:00,11/02/2026 10:00,55501,11/02/2026 11:00,11/02/2026 12:00,55502
```

## 4. Modify existing events: use `update-events.csv`

Choose either:

- **Edit a fresh export:** save it as `update-events.csv`, retaining IDs and editing the desired fields.
- **Make a small update file:** include `item_id` and only the fields you want to modify. This avoids supplying old values for unrelated fields.

Each event ID must be a positive whole number and appear only once among calendar event rows. Use the exported `item_id`; `event_id` is an accepted alternative header. Do not include both headers.

### Update columns and value formats

Only the ID column is required. Omit other columns or leave cells blank to preserve their current values.

| Column | Value format |
| --- | --- |
| `item_id` or `event_id` | Existing Canvas calendar event ID. A course ID cannot identify an event here. |
| `title` | New title. |
| `description` | Plain text or HTML. `__CLEAR__` removes the description. `new_description` is an accepted alternative header. |
| `start_at`, `end_at` | ISO date/time **with timezone**, e.g. `2026-11-02T09:00:00-08:00` or `2026-11-02T17:00:00Z`. End must not precede start. |
| `location_name`, `location_address` | Text, or `__CLEAR__` to empty the field. |
| `all_day` | `true`/`false`, `yes`/`no`, or `1`/`0`. |
| `context_code` | Retain the exported identifier unless intentionally moving the event. Course examples: `course_12345`; section examples: `course_section_55501`. |

**Example: change descriptions only:**

```csv
item_id,description
90001,"Bring a laptop, notebook, and pen."
90002,__CLEAR__
```

**Example: change one event's title and schedule:**

```csv
item_id,title,start_at,end_at
90001,Revised orientation,2026-11-02T10:00:00-08:00,2026-11-02T11:00:00-08:00
```

**Preview, then apply:**

```powershell
python -m canvas_events update update-events.csv
python -m canvas_events update update-events.csv --apply
```

`update` never creates events. With no input path, it looks for `export-events.csv` in the current directory, then in `canvas_events/`.

### Using Excel and retaining export columns

Update also accepts `.xlsx` with the same headers. Keep IDs as whole-number text and dates as text with their offsets; do not use Excel date cells that strip the timezone or formulas as update values.

```powershell
python -m canvas_events update update-events.xlsx --sheet "Events"
python -m canvas_events update update-events.xlsx --sheet "Events" --apply
```

Without `--sheet`, the active worksheet is used.

You can retain all original export columns. `course_id`, `course_name`, `source`, `created_at`, `updated_at`, and `workflow_state` are ignored during updates. `due_at`, `assignment_type`, and `html_url` identify reference assignment rows; preserve those markers if keeping assignment rows. Changing `due_at` does not update an assignment. Unsupported extra columns and duplicate headers are rejected.

Every nonblank editable value is compared with live Canvas. An old full export can overwrite later edits in Canvas. Use a fresh export or a minimal update file. Older exports that incorrectly labeled Vancouver local times with `Z` must be replaced with fresh exports.

### Modifying section events

Use the exported section child's `item_id`. Edit its `start_at` and `end_at` to change that section's schedule.

**Titles, descriptions, location names, and location addresses are shared across sibling sections.** Changing one of these fields on a section row changes it for all siblings through their parent. Conflicting edits to shared fields are rejected before writes.

Changing a section row's `context_code` to another `course_section_ID` reassigns its schedule while preserving siblings. The destination section must not already exist under that parent. Re-export after applying: section replacement can change child event IDs. Section rows support individual events only (`which=one`), without `rrule` or `sections`.

### Advanced update columns

| Column | Format / restrictions |
| --- | --- |
| `blackout_date` | Boolean, using the same values as `all_day`. |
| `time_zone_edited` | Timezone text. |
| `rrule` | Recurrence rule text; unavailable on section child rows. |
| `which` | `one` (default), `all`, or `following`, selecting recurrence scope. |
| `sections` | Complete JSON section schedule on a parent course event row. See below. |

For `sections`, use the parent course event ID and a JSON list containing every section to retain. Each entry needs `context_code`, `start_at`, and `end_at`. Empty lists are rejected. Example of the content of **one spreadsheet cell**:

```json
[{"context_code":"course_section_55501","start_at":"2026-11-02T09:00:00-08:00","end_at":"2026-11-02T10:00:00-08:00"}]
```

In a CSV, quote this cell and double every embedded double quote. Omitted sibling sections are omitted from this replacement schedule. Changing only `context_code` cannot convert a course-wide event into a section event. Ordinary calendar moves are restricted for section events and appointments.

## 5. Delete events: course list in, all course calendar events removed

Prepare a course list in the same format as export. Use a separate name such as `delete-course-ids.csv` to make the selected scope clear:

```csv
course_id
12345
```

**Preview the event list, then delete:**

```powershell
python -m canvas_events delete --courses delete-course-ids.csv
python -m canvas_events delete --courses delete-course-ids.csv --apply
```

This command deletes **all calendar events returned for each listed course**, including section children when their parent is deleted. It does not delete assignments. It does not accept an event-ID list or an edited event export for selective deletion. Removing a row from an update file does not delete that event.

With no `--courses`, delete looks for `course_ids.csv` in the current directory, then in `canvas_events/`.

## 6. Preview, apply, and verify

Import, update, and delete make no changes without `--apply`. Update and delete previews read live Canvas and require authentication. Update plans and validates all rows before any writes. Applying rebuilds that plan against live data; it does not replay a saved preview.

After applying, export again and verify the result. Writes are separate requests with no cross-event rollback. If a run fails, earlier requests may already have succeeded. Check Canvas and preview again before retrying, especially when creating events or after a timeout. Writes are not automatically retried.

Use `python -m canvas_events --help` to list commands. Each command has its own help:

```powershell
python -m canvas_events export --help
python -m canvas_events import --help
python -m canvas_events update --help
python -m canvas_events delete --help
```

## Project files and cleanup

| Location | Purpose |
| --- | --- |
| `canvas_events/__main__.py` | Command selection and help. |
| `canvas_events/__init__.py` | Marks the folder as a Python package. |
| `canvas_events/common.py` | Shared authentication, requests, and default input lookup. |
| `canvas_events/export.py`, `create.py`, `update.py`, `delete.py` | Implement the four commands. `create.py` implements the public `import` command. |
| `examples/` | Fictional input templates committed with the project. |
| `requirements.txt` | Dependencies for the calendar commands. |

Keep the implementation files, examples, requirements, README, `.gitignore`, and `.git/` (repository history).

`canvas_events/modify-events-csv-for-workload.py` is an optional, separate reporting utility. It requires `pandas`, which is outside the core requirements, and reads `input.csv` and writes `output.csv` in the current directory. It splits pipe-delimited descriptions and expands instructor rows. Its title-based section assumptions need review for current exports. Its output has extra columns and potentially duplicate IDs, so it is not update input. Remove this utility only if you no longer need workload reporting.

Generated `__pycache__/` folders and compiled Python files can be removed and are ignored by Git. Local CSV inputs, exports, and edited copies can be removed only after their data is no longer needed or archived. The old hyphenated script folders have been retired; use the module commands above.

`.gitignore` excludes local CSVs while allowing `examples/*.csv`. Ignore rules do not untrack files already in Git. Review `git status` before committing: include new implementation files and requirements alongside deletions of the retired scripts.
