# Self-Healing AI

## What is it?

Self-Healing AI is an autonomous incident detection and code remediation tool. It actively monitors your application for runtime errors, analyzes tracebacks using a Large Language Model (Google Gemini), automatically generates a patch, validates it safely, and attempts to restore your service without human intervention. Instead of just notifying you of an error, it provides a working fix.

## How it works

The system operates continuously in the background, closing the loop from failure to recovery through the following steps:

Error
→ Watcher
→ AI diagnosis
→ Validation
→ Pytest
→ Patch
→ Health Check
→ Rollback if necessary
→ Git branch
→ GitHub Pull Request

## Architecture

The project consists of several core components working together seamlessly:

- **app.py**: The target application being monitored. In this MVP, it runs a FastAPI service.
- **watcher.py**: Continuously monitors the configured log file for tracebacks, orchestrating the healing process when an error is detected.
- **ai_engine.py**: Communicates with the Google Gemini LLM to diagnose the traceback and generate the required source code fix.
- **validator.py**: Validates the AI-generated patch locally using static analysis (e.g., `py_compile`) and test suites before applying it.
- **git_module.py**: Manages creating local branches, committing patches, and handling GitHub integration for pull requests.
- **self_healing_cli.py**: The primary developer interface for managing the self-healing workflow (init, start, status).

## Requirements

This project requires:
- Python 3.8+
- The dependencies listed in `requirements.txt` (including FastAPI, Uvicorn, Watchdog, Requests, and Psutil)
- Git (for branch creation and patch versioning)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/rajdeep-r24/Self-Healing-AI.git
   cd Enterprise-Self-Healing
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

The AI engine and GitHub integration rely on external APIs. You must configure your environment variables using a `.env` file. 

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` to include your actual keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=your_primary_model_here
GEMINI_FALLBACK_MODEL=your_fallback_model_here
GITHUB_TOKEN=your_github_token_here
```

**⚠️ CRITICAL WARNING: DO NOT commit your `.env` file. It contains highly sensitive secrets. Our `.gitignore` is configured to prevent this, but always verify before pushing.**

## CLI Usage

The Self-Healing AI is controlled via a simple command-line interface.

Initialize the project in the current directory (creates `.self-healing/config.json`):
```bash
python self_healing_cli.py init
```

Check the status of your configuration and environment:
```bash
python self_healing_cli.py status
```

Start the autonomous watcher in the background:
```bash
python self_healing_cli.py start
```

If a Windows wrapper exists, you may be able to use `self-healing status` directly.

## Example Workflow

A realistic developer workflow looks like this:

1. You clone the repo, install dependencies, and configure your `.env` file.
2. You run `python self_healing_cli.py init` to configure the project safely.
3. You start the watcher in a background terminal using `python self_healing_cli.py start`.
4. You start your local dev server (`uvicorn app:app --reload`) in another terminal.
5. You work normally. If you trigger an unhandled exception, the watcher immediately detects it, queries the AI, validates the fix, and hot-patches the server while creating a Git branch for your review.

## Safety Mechanisms

Autonomous code generation carries risks. We mitigate them with multiple layers of safety:

- **Syntax Validation**: The patch is compiled via `py_compile` to ensure valid Python syntax before any execution.
- **Shadow Pytest Validation**: If a test suite exists, tests are executed against the temporary AI patch. Failing patches are rejected.
- **Backup**: A backup of the broken source file is created immediately prior to patching.
- **Health Check**: After hot-patching, the system performs an HTTP health check to ensure the application starts and functions correctly.
- **Rollback**: If the health check fails, the AI-generated patch is discarded and the original broken source is perfectly restored.
- **Git Branch**: All successful patches are committed to a safe, isolated `ai-fix-*` branch, preventing interference with your working tree.
- **Human-Reviewed Pull Request**: The AI never pushes directly to `main`. It opens a Pull Request so a human developer can review the code.

## GitHub Integration

The AI respects standard repository workflows. It **does not directly modify `main`**.

When a fix is generated and passes local validation, a new `ai-fix-[timestamp]` branch is created. The fix is pushed to origin, and a Pull Request is automatically created against the `main` branch. This allows you to review, modify, or decline the AI's patch using standard code review processes.

## Limitations

Please be aware of the following system constraints:

- **API Limits**: LLM availability, latency, and rate limits (e.g., 429 errors on the free tier) can slow down or temporarily halt healing.
- **AI Hallucinations**: AI-generated fixes are "best effort" and are not guaranteed to be correct or logically sound.
- **Test Coverage Requirement**: Projects without comprehensive automated test suites have weaker validation, increasing the reliance on the post-patch Health Check.
- **Human Oversight**: Human review of the generated Pull Requests remains critically important before merging to production.
