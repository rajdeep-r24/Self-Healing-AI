import shutil
import os

def reset():
    print("Resetting demo to broken state...")
    
    if os.path.exists("app_broken.py"):
        shutil.copy("app_broken.py", "app.py")
        print("[SUCCESS] Restored broken app.py")
    else:
        print("[ERROR] Could not find app_broken.py!")
        
    if os.path.exists("logs/server.log"):
        with open("logs/server.log", "w") as f:
            f.write("")
        print("[SUCCESS] Cleared server.log")
        
    print("Demo reset complete! You can now trigger the bug again.")

if __name__ == "__main__":
    reset()
