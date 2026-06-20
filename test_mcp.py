import sys
from instagram_client import InstagramClientWrapper

def test_imports():
    try:
        import instagrapi
        import fastmcp
        print("Imports: OK", file=sys.stderr)
        return True
    except ImportError as e:
        print(f"Imports: FAILED - {e}", file=sys.stderr)
        return False

def test_wrapper():
    try:
        wrapper = InstagramClientWrapper(session_path="test_session.json")
        status = wrapper.is_logged_in()
        print(f"Status check: OK (Logged in: {status})", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Wrapper initialization: FAILED - {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    print("Running quick local verification...", file=sys.stderr)
    imports_ok = test_imports()
    wrapper_ok = test_wrapper()
    if imports_ok and wrapper_ok:
        print("\nAll local checks passed. Ready to start MCP server.", file=sys.stderr)
        sys.exit(0)
    else:
        print("\nSome checks failed.", file=sys.stderr)
        sys.exit(1)
