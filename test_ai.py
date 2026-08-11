from ai_engine import diagnose_and_fix

def test_ai():
    traceback = "KeyError: 'user_name'"
    source = """user_data = {"username": "admin"}
greeting = f"Hello, {user_data['user_name']}!"
"""
    print("Testing AI Engine independently...")
    try:
        result = diagnose_and_fix(traceback, source)
        print("\n--- TEST RESULT ---")
        print("Diagnosis:", result['diagnosis'])
        print("Fixed Code:\n", result['fixed_code'])
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    test_ai()
