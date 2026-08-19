import os
import sys
import time
import threading
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

class TUIDashboard:
    def __init__(self, project_root=".", log_file="logs/server.log", is_demo_mode=False, model_name="gemini-2.5-flash"):
        self.project_root = project_root
        self.log_file = log_file
        self.is_demo_mode = is_demo_mode
        self.model_name = model_name
        self.is_tty = sys.stdout.isatty()
        
        self.stages = [
            {"id": "interceptor", "name": "1. Error Interceptor", "status": "PENDING", "info": "", "duration": None},
            {"id": "ai", "name": "2. AI Diagnostic Engine", "status": "PENDING", "info": f"Model: {model_name}", "duration": None},
            {"id": "validator", "name": "3. Syntax Validator", "status": "PENDING", "info": "py_compile AST check", "duration": None},
            {"id": "pytest", "name": "4. Pytest Regression Shield", "status": "PENDING", "info": "Bounded test suite", "duration": None},
            {"id": "patch", "name": "5. Atomic Hot-Patch", "status": "PENDING", "info": "Backup & safe write", "duration": None},
            {"id": "health", "name": "6. Short-Polling Health Check", "status": "PENDING", "info": "HTTP 200 verification", "duration": None},
            {"id": "git", "name": "7. Git Branch & GitHub PR", "status": "PENDING", "info": "Local commit & PR creation", "duration": None},
        ]
        self.active_stage_idx = None
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.current_activity = "Waiting for application error..."
        self.start_time = None
        self.stage_start_time = None
        self.running = False
        self._thread = None
        self._lock = threading.Lock()
        self.rendered_lines = 0

    def print_banner(self):
        mode_badge = f"{Fore.YELLOW}[DEMO MODE]{Style.RESET_ALL}" if self.is_demo_mode else f"{Fore.CYAN}[PRODUCTION]{Style.RESET_ALL}"
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.BRIGHT}{Fore.WHITE}             ⚡ ENTERPRISE SELF-HEALING AI — LIVE MONITOR ⚡                {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║  {Fore.GREEN}● MONITORING ACTIVE{Fore.WHITE}  |  Log: {Fore.YELLOW}{self.log_file}{Fore.WHITE}  |  {mode_badge}             {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")

    def start_repair(self, error_desc, target_file):
        with self._lock:
            self.start_time = time.time()
            self.running = True
            for s in self.stages:
                s["status"] = "PENDING"
                s["duration"] = None
            self.stages[0]["status"] = "PASS"
            self.stages[0]["info"] = f"{error_desc} in {os.path.basename(target_file)}"
            self.stages[0]["duration"] = 0.001
            self.current_activity = f"Interception complete for {os.path.basename(target_file)}"
            self.rendered_lines = 0

        self.render()
        self._start_spinner_thread()

    def _start_spinner_thread(self):
        if not self.is_tty:
            return
        if self._thread and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self._spinner_loop, daemon=True)
        self._thread.start()

    def _spinner_loop(self):
        while self.running:
            time.sleep(0.1)
            with self._lock:
                self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            self.render()

    def set_stage_active(self, stage_id, activity_msg, est_time=""):
        with self._lock:
            for idx, s in enumerate(self.stages):
                if s["id"] == stage_id:
                    self.active_stage_idx = idx
                    s["status"] = "RUNNING"
                    if est_time:
                        s["info"] = f"Est: ~{est_time}"
                    break
            self.stage_start_time = time.time()
            self.current_activity = activity_msg
        self.render()

    def set_stage_complete(self, stage_id, success=True, info_msg="", duration=None):
        with self._lock:
            if duration is None and self.stage_start_time:
                duration = time.time() - self.stage_start_time
            for s in self.stages:
                if s["id"] == stage_id:
                    s["status"] = "PASS" if success else "FAIL"
                    s["duration"] = duration
                    if info_msg:
                        s["info"] = info_msg
                    break
            self.stage_start_time = None
        self.render()

    def update_activity(self, activity_msg):
        with self._lock:
            self.current_activity = activity_msg
        self.render()

    def finish_repair(self, success=True, summary_msg=""):
        self.running = False
        if self._thread:
            self._thread.join(timeout=0.2)
            
        with self._lock:
            total_duration = time.time() - self.start_time if self.start_time else 0.0
            self.render()
            print()
            if success:
                print(f"{Fore.GREEN}{Style.BRIGHT}✔ [HEALER] Recovery successful ({total_duration:.1f}s) — System fully operational!{Style.RESET_ALL}")
                if summary_msg:
                    print(f"  {Fore.CYAN}▶ {summary_msg}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}{Style.BRIGHT}✖ [HEALER] Recovery aborted safely ({total_duration:.1f}s) — State restored from backup.{Style.RESET_ALL}")
                if summary_msg:
                    print(f"  {Fore.YELLOW}▶ {summary_msg}{Style.RESET_ALL}")
            print(f"\n{Fore.GREEN}● Log monitoring active. Ready for next event...{Style.RESET_ALL}\n")

    def render(self):
        if not self.is_tty:
            return

        lines = []
        lines.append(f"{Style.BRIGHT}{Fore.WHITE}  PIPELINE STAGE                   STATUS          ELAPSED / DETAILS{Style.RESET_ALL}")
        lines.append(f"  {Fore.CYAN}{'─' * 70}{Style.RESET_ALL}")

        spinner = self.spinner_chars[self.spinner_idx]
        
        for idx, s in enumerate(self.stages):
            name = s["name"].ljust(30)
            status = s["status"]
            info = s["info"]
            
            if status == "PASS":
                dur_str = f"{s['duration']:.2f}s" if s['duration'] is not None else ""
                badge = f"{Fore.GREEN}{Style.BRIGHT}[PASS]{Style.RESET_ALL}"
                icon = f"{Fore.GREEN}✔{Style.RESET_ALL}"
                detail = f"{Fore.GREEN}{dur_str} {Style.RESET_ALL}({info})" if info else f"{Fore.GREEN}{dur_str}{Style.RESET_ALL}"
            elif status == "RUNNING":
                elapsed = time.time() - self.stage_start_time if self.stage_start_time else 0.0
                badge = f"{Fore.YELLOW}{Style.BRIGHT}[RUNNING]{Style.RESET_ALL}"
                icon = f"{Fore.YELLOW}{spinner}{Style.RESET_ALL}"
                detail = f"{Fore.YELLOW}⏳ {elapsed:.1f}s {Style.RESET_ALL}({info})"
            elif status == "FAIL":
                dur_str = f"{s['duration']:.2f}s" if s['duration'] is not None else ""
                badge = f"{Fore.RED}{Style.BRIGHT}[FAIL]{Style.RESET_ALL}"
                icon = f"{Fore.RED}✖{Style.RESET_ALL}"
                detail = f"{Fore.RED}{dur_str} {Style.RESET_ALL}({info})"
            else: # PENDING
                badge = f"{Fore.LIGHTBLACK_EX}[PENDING]{Style.RESET_ALL}"
                icon = f"{Fore.LIGHTBLACK_EX}○{Style.RESET_ALL}"
                detail = f"{Fore.LIGHTBLACK_EX}--{Style.RESET_ALL}"

            lines.append(f"  {icon} {name} {badge.ljust(18)} {detail}")

        lines.append(f"  {Fore.CYAN}{'─' * 70}{Style.RESET_ALL}")
        lines.append(f"  {Style.BRIGHT}{Fore.WHITE}CURRENT ACTIVITY:{Style.RESET_ALL}")
        lines.append(f"  {Fore.CYAN}▶ {self.current_activity[:72]}{Style.RESET_ALL}")

        # Erase previous frame and redraw in place
        if self.rendered_lines > 0:
            sys.stdout.write(f"\033[{self.rendered_lines}F")
        for line in lines:
            # Clear line and print
            sys.stdout.write(f"\033[2K{line}\n")
        sys.stdout.flush()
        self.rendered_lines = len(lines)

# Global singleton or factory
_dashboard_instance = None

def get_dashboard(project_root=".", log_file="logs/server.log", is_demo_mode=False, model_name=""):
    global _dashboard_instance
    if _dashboard_instance is None:
        _dashboard_instance = TUIDashboard(project_root, log_file, is_demo_mode, model_name)
    return _dashboard_instance
