---
sidebar_position: 4
title: Migration
---

# Migrating a legacy configuration

Earlier TestBench requirement wrappers were configured with a Jira `.conf` file or an Excel
`.properties` file. The `migrate` command reads one of those files and writes an equivalent
`config.toml` for this service, so you do not have to re-enter settings that the old file
already holds.

```bash
testbench-requirement-service migrate --from PATH [--path PATH] [--type excel|jira]
```

:::note
Only the Jira and Excel readers have a legacy wrapper format. There is nothing to migrate for
the JSONL and SQL readers — configure them with [`init`](cli-commands.md#init).
:::

---

## Before you start

1. **Locate the legacy file.** It is the file the old wrapper was started with — a `.conf` for
   Jira, a `.properties` for Excel. In an RMProxy installation it usually sits below
   `C:\imbus\TestBench\iTB_RMProxy\`.
2. **Install the matching extra.** The migration validates against the reader model, and the
   Jira flow refuses to run without the Jira dependencies:

   ```bash
   pip install "testbench-requirement-service[jira]"    # or [excel]
   ```

   See [Installation](getting-started/installation.md).
3. **Run it on a machine that can see the data.** The Excel reader model checks that
   `requirementsDataPath` exists, so migrate from a host with that directory or share mounted.
4. **Keep the old file.** `migrate` only reads it; it is never modified. Leave it in place until
   the new service has served requirements successfully.
5. **Note the repository name.** The `name` from the RMProxy
   [wrapper configuration](testbench-integration.md#1-wrapper-configuration) is the identifier
   TestBench knows the repository by. It lives in RMProxy, not in the converted file, so leave
   it unchanged.

---

## What the command does

1. Detects the legacy format from the file extension (`.conf` → Jira, `.properties` → Excel).
2. Parses the file with the parser for that format. A line it cannot read, or a key set twice
   to two different values, aborts the migration and names the file and line number.
3. Asks for the settings the legacy format never carried — the service credentials, and for
   Jira the authentication method.
4. Validates the result against the same reader model the service loads at startup, filling in
   documented defaults for everything the legacy file does not mention.
5. Lists the legacy entries that have no equivalent in the new configuration, so a setting
   that mattered can be applied by hand.
6. Writes the TOML file.

The conversion runs to completion **before anything is written**. Cancelling a prompt, or a
value the service would reject, aborts the migration and leaves an existing configuration
exactly as it was.

---

## Migrating a Jira wrapper (`.conf`)

```bash
testbench-requirement-service migrate --from jira.conf
```

A legacy `.conf` file is a list of `key: value` lines; `#` starts a comment and surrounding
double quotes are stripped:

```conf
# jira.conf
url: http://jiraserver:8080/
baseline: fixVersions
owner: assignee
baseline_jql: project = "{project}" AND fixVersion = "{baseline}"
current_baseline_jql: project = "{project}"
render_description: true
jira.username: jira-user@example.com
```

### What is carried over

| Legacy key             | TOML option            | Notes |
|---|---|---|
| `url`                  | `server_url`           | Also pre-fills the server URL prompt. |
| `baseline`             | `baseline_field`       | Jira field the baselines/versions are read from. |
| `owner`                | `owner_field`          | Jira field the requirement owner is read from. |
| `baseline_jql`         | `baseline_jql`         | JQL template for the requirements of a baseline. |
| `current_baseline_jql` | `current_baseline_jql` | JQL template for the current (unbaselined) requirements. |
| `render_description`   | `rendered_fields`      | A set flag adds `"description"` to the fields delivered as rendered HTML. |

`jira.username` (also `jira.user` / `jira.login`) is used as the **default for the username
prompt**, not written directly — which credentials are needed depends on the authentication
method you choose.

Every other key in the `.conf` is ignored — and named when the migration finishes, so you can
see what was left behind. Options the file says nothing about are written with the reader
model's documented defaults, so the generated file is complete and self-explanatory.

:::note[`render_description` becomes a list entry]
The legacy wrapper had a single flag for a single field. The reader generalizes it to
`rendered_fields`, a list of the fields it delivers as rendered HTML, so
`render_description: true` is converted to `rendered_fields = ["description"]`. `true`, `yes`,
`on` and `1` all count as set; anything else — and a `.conf` that does not mention the flag —
yields the default `rendered_fields = []`. Further fields can be added to the list by hand; see
[Requirements & baselines settings](readers/jira.md#requirements--baselines-settings).
:::

:::note[`baseline` and `owner` are renamed]
The reader calls these settings `baseline_field` and `owner_field`, so the conversion renames
them. A `.conf` that says nothing about them yields the model defaults `baseline_field =
"fixVersions"` and `owner_field = "assignee"`. See
[Requirements & baselines settings](readers/jira.md#requirements--baselines-settings).
:::

### What you are asked for

| Prompt | Why |
|---|---|
| **Service credentials** (username, password) | They protect this service's own HTTP API and have no counterpart in the legacy wrapper. A fresh `password_hash` and `salt` are derived from what you enter. |
| **Jira authentication** (`auth_type` and the credentials it implies) | The legacy wrapper stored its Jira credentials outside the `.conf`. |

The authentication prompts are the same ones [`configure`](cli-commands.md#configure) uses,
including the choice of `basic`, `token`, `oauth1`, `oauth2 2LO (service account)` and
`oauth2 3LO (user account)` — see [Authentication methods](readers/jira.md#authentication-methods).

For the OAuth2 flows:

- The **client secret** is written to `.env` as `JIRA_OAUTH2_CLIENT_SECRET`, never into the
  TOML file.
- For **3LO**, the browser-based OAuth wizard runs when no refresh token is available, and the
  resulting refresh token is stored in the token cache rather than in the configuration.

---

## Migrating an Excel wrapper (`.properties`)

```bash
testbench-requirement-service migrate --from genericexcel.properties
```

A legacy `.properties` file is a list of `key=value` lines; `#` and `!` start a comment:

```properties
# genericexcel.properties
requirementsDataPath=C:/requirements/excel/
columnSeparator=;
arrayValueSeparator=,
baselineFileExtensions=.tsv,.csv,.txt
useExcelDirectly=false
worksheetName=Tabelle1
dateFormat=yyyy-MM-dd HH:mm:ss
header.rowIdx=1
data.rowIdx=2

requirement.id=1
requirement.version=6
requirement.name=3
requirement.owner=4
requirement.description.1=8
requirement.description.2=9

udf.count=1
udf.attr1.name=Risiko
udf.attr1.type=string
udf.attr1.column=11
```

### What is carried over

The Excel reader uses the legacy key names as its own field aliases, so the whole file is
converted and the **generated TOML keeps the same key spelling** — dotted keys are simply
quoted:

```toml
[testbench-requirement-service.reader_config]
requirementsDataPath = "C:\\requirements\\excel"
columnSeparator = ";"
arrayValueSeparator = ","
useExcelDirectly = false
"requirement.id" = 1
"requirement.version" = 6
"requirement.name" = 3
"requirement.description.1" = 8
"requirement.description.2" = 9
"udf.count" = 1
"udf.attr1.name" = "Risiko"
"udf.attr1.type" = "STRING"
"udf.attr1.column" = 11
```

Note what the conversion does beyond copying:

- Values arrive **typed** — column indices become integers, `useExcelDirectly` a boolean, and
  `udf.attr<n>.type` is normalized to upper case.
- `requirementsDataPath` is resolved and written as an **absolute** path.
- Every option the file omits is written with its documented default (`bufferMaxAgeMinutes`,
  `requirement.folderPattern`, and so on), so the result is a full reference of what the reader
  will do.
- **Unknown keys are ignored** — settings from the old wrapper that the reader has no option
  for simply do not appear in the result.

The only prompt is for the **service credentials**; everything else comes from the file.

:::tip[Per-project `.properties` files]
A `<ProjectName>.properties` file inside a project directory does not need migrating. The Excel
reader reads it at runtime in its original spelling — see
[Project-specific overrides](readers/excel.md#project-specific-overrides).
:::

---

## Choosing the output path and the source type

| Option | Description | Default |
|---|---|---|
| `--from PATH` | Legacy `.conf` or `.properties` file to convert (required) | — |
| `--path PATH` | Configuration file to write | `config.toml` |
| `--type [excel\|jira]` | Legacy source type | detected from the file extension |

Pass `--type` when the file has been renamed and its extension no longer identifies the format:

```bash
# Write somewhere other than the working directory
testbench-requirement-service migrate --from jira.conf --path /etc/requirement-service/config.toml

# The extension no longer says which wrapper this is
testbench-requirement-service migrate --from wrapper.txt --type jira
```

If the target file already exists you are asked to confirm, and the existing file is renamed to
`config.toml.backup` — timestamped when a backup is already present — before the new one is
written.

---

## After migrating

1. **Review the generated file.** It contains every option, including the defaults that were
   filled in, so it is worth reading once against the [Configuration](configuration.md)
   reference:

   ```bash
   testbench-requirement-service configure --view
   ```

2. **Adjust anything the legacy format could not express** — logging, SSL, `host` / `port`,
   per-project overrides and, for Jira, `baseline_field` / `owner_field`:

   ```bash
   testbench-requirement-service configure
   ```

3. **Start the service** and check the log for a successful reader initialization:

   ```bash
   testbench-requirement-service start
   ```

4. **Reconnect TestBench.** Point the RMProxy
   [service settings](testbench-integration.md#2-service-settings) at the host and port the
   migrated service listens on, restart the RMProxy, then use *Test Connection* on the
   repository in TestBench. The full procedure is on the
   [TestBench Integration](testbench-integration.md) page.

---

## Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `Cannot tell the legacy format of '<file>' from its extension.` | The file is neither `.conf` nor `.properties`. | Pass `--type jira` or `--type excel`. |
| `<file> line <n>: expected 'key: value', got '<line>'` | The line carries no separator. When it uses the other format's separator the message says so — usually a wrapper file migrated with the wrong `--type`. | Fix the line, comment it out with `#`, or pass the `--type` the message names. Nothing was written. |
| `<file> line <n>: '<key>' is set twice, to '<a>' and '<b>'.` | The legacy file gives one key two different values, so there is no telling which one to migrate. | Remove one of the two entries and run `migrate` again. |
| `Cannot convert the Excel .properties file: requirementsDataPath: ... not found` | The requirements directory does not exist on this machine, or a Windows path was written with single backslashes. | Migrate where the data is reachable; use forward slashes (`C:/requirements/`) or double backslashes. |
| `Cannot convert the ... file: <field>: <message>` | A converted value is not valid for the reader model — e.g. a column index below 1, or a missing mandatory key. | Correct the named key in the legacy file and run `migrate` again. Nothing was written. |
| `Jira authentication setup was cancelled` / `Service credentials setup was cancelled` | A prompt was aborted. | Re-run the command; the existing configuration was not touched. |
| The Jira extra is reported as missing | The Jira dependencies are not installed, so the authentication prompts cannot run. | `pip install "testbench-requirement-service[jira]"` |

:::note
The service credentials are asked for **before** the legacy file is validated. If the
conversion then fails, the password you entered is simply discarded along with the rest of the
attempt — nothing is written.
:::

### Entries that were not carried over

A legacy file may configure things the new reader has no equivalent for. Those entries are
listed once every prompt is answered, immediately before the file is written:

```text
════════════════════════════════════════════════════════════
⚠️  2 legacy setting(s) were NOT carried over
════════════════════════════════════════════════════════════
  • password
  • wrapper.class

Nothing in the new configuration reads them. The legacy file is unchanged,
so anything that still matters can be applied to the new file by hand.
════════════════════════════════════════════════════════════
```

Apart from those keys the migration is complete — nothing else was dropped silently.

### Rolling back

The migration writes exactly one file. To go back, restore the `config.toml.backup*` file that
`migrate` created, or delete the generated configuration — the legacy `.conf` / `.properties`
file is untouched and can be migrated again at any time.

---

## See also

- [CLI reference for `migrate`](cli-commands.md#migrate)
- [Excel reader](readers/excel.md) and [Jira reader](readers/jira.md) — what every converted option means
- [TestBench Integration](testbench-integration.md) — wiring the migrated service into RMProxy
