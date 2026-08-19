import os
from ai_engine import diagnose_and_fix

if 'EVALUATION_MODE' in os.environ:
    del os.environ['EVALUATION_MODE']

try:
    code = """user_data = {"username": "admin"}
greeting = f"Hello, {user_data['user_name']}!" """
    res = diagnose_and_fix("KeyError: user_name", code)
    print("RESPONSE_SUCCESS")
    print("DIAGNOSIS:", res["diagnosis"])
    print("FIXED_CODE:", res["fixed_code"])
except Exception as e:
    print("RESPONSE_FAILED:", e)
