# Self-Healing AI: Developer Guide

This guide covers the day-to-day operations and configurations for working with the Self-Healing AI tool locally.

## 1. Installation

1. Clone the repository and navigate into the `Enterprise-Self-Healing` directory.
2. Ensure you have Python 3.8+ installed.
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 2. Initialization

Before the Self-Healing AI can monitor your project, it must be initialized.

```bash
python self_healing_cli.py init
```

This command will:
- Detect your current project directory.
- Verify if you are operating within a Git repository (required for local branching and Pull Request creation).
- Create a `.self-healing/config.json` configuration file.

If a configuration already exists, `init` will safely retain your existing settings without silently destroying them.

## 3. Starting the Watcher

The watcher operates independently of your application. You typically run your web service (e.g., FastAPI/Uvicorn, Django, Flask) in one terminal, and the watcher in another.

To start the watcher:
```bash
python self_healing_cli.py start
```

The CLI will:
1. Verify that your `.self-healing/config.json` exists and is valid.
2. Validate that the configured `log_file` path exists or create its parent directories.
3. Start the background monitoring process.

If your configuration is missing or invalid, the CLI will fail gracefully with actionable instructions instead of a cryptic stack trace.

## 4. Configuration

### `config.json`

Your `.self-healing/config.json` specifies the project boundaries and the target log file. It must only contain path information and non-sensitive options.

```json
{
    "project_root": ".",
    "log_file": "logs/server.log"
}
```

*Note: Path traversal (e.g., using `../`) and absolute paths in `log_file` are explicitly blocked for safety.*

### Environment Variables (`.env`)

Secrets (such as API keys and GitHub tokens) **must never** be stored in `config.json`. They belong in `.env`.

Copy `.env.example` to `.env` and fill in your keys:
- `GEMINI_API_KEY`: Your Google Gemini API Key.
- `GITHUB_TOKEN`: Your GitHub Personal Access Token (fine-grained access for Pull Requests).

Do NOT commit `.env` to Git.

## 5. Understanding Healing Output

When your application crashes and writes a traceback to your monitored log file, the watcher takes over. You will see output reflecting these distinct phases:

1. **[WATCHER] Error detected**: The traceback has been intercepted.
2. **[AI] Analyzing failure...**: The stack trace and relevant source files are sent to the LLM.
3. **[VALIDATOR] Checking syntax...**: The AI generated a patch. It is being tested locally using `py_compile` or `pytest`.
4. **[HEALER] Patch applied**: The file was patched. A backup is created safely before any modification.
5. **[HEALER] Health check...**: A local HTTP request or verification step ensures the application restarted without catastrophic failure.
6. **[GIT] Branch created**: A safe branch is created, and the patch is pushed to GitHub.

If the health check or local validation fails:
- **[ROLLBACK] Previous version restored**: The broken patch is reverted, and your code goes back to exactly how you left it.

## 6. GitHub PR Workflow

The self-healing process never force-pushes to your `main` branch or current working tree without explicit review. 

When a successful fix is generated:
1. The tool creates a local Git branch: `ai-fix-<timestamp>`.
2. It pushes this branch to origin.
3. It uses your `GITHUB_TOKEN` to open a Pull Request against the `main` branch.
4. You receive the PR, review the code, and merge it if it is correct.

If the network is down or the GitHub integration fails, your local branch and fix still persist without breaking the overall process.

## 7. Troubleshooting

- **[ERROR] Project is not initialized**: You forgot to run `self_healing_cli.py init`.
- **[ERROR] Invalid .self-healing/config.json**: Your config file is improperly formatted JSON. Please fix it or re-initialize.
- **[GIT] Repository not detected**: Ensure you ran `git init` or cloned the repository. The AI cannot branch or create PRs without a `.git` folder.
- **[HEALER] Process failed (API Limits)**: You may have hit a rate limit (e.g., 429 RESOURCE_EXHAUSTED). The AI will fail safely. Check your quota or wait before triggering another fix.
