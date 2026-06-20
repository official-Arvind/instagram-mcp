import sys
import os

SESSION_ID = "77733115599:n9Dr5bZ8QCxlJb:29:AYiKwWusUWQpxqBq-kgmz_TRavt-xu33DKD30soghQ"
USERNAME = None  # Will be fetched after login
IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_post.png")
CAPTION = """🤖 AI just took the wheel 🚀

This post was autonomously created and published by an AI agent using the Instagram Control MCP Server — built from scratch with Python, instagrapi & fastmcp.

No hands on the keyboard. Pure AI. 🧠⚡

#AI #MCP #ModelContextProtocol #AIAutomation #Python #Instagrapi #BuildInPublic #ArtificialIntelligence #TechDemo"""

def main():
    from instagrapi import Client
    
    print("Initializing Instagram client...", file=sys.stderr)
    cl = Client()

    print(f"Logging in via session ID...", file=sys.stderr)
    try:
        cl.login_by_sessionid(SESSION_ID)
    except Exception as e:
        print(f"Login failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch own user info to verify
    try:
        user = cl.user_info(cl.user_id)
        print(f"Logged in as: @{user.username} ({user.full_name})", file=sys.stderr)
        print(f"Followers: {user.follower_count} | Following: {user.following_count} | Posts: {user.media_count}", file=sys.stderr)
    except Exception as e:
        print(f"Could not verify login: {e}", file=sys.stderr)
        sys.exit(1)

    # Save session for future use
    print("Saving session...", file=sys.stderr)
    cl.dump_settings("instagram_session.json")
    
    # Now upload the image
    if not os.path.exists(IMAGE_PATH):
        print(f"Image not found at {IMAGE_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"Uploading photo from: {IMAGE_PATH}", file=sys.stderr)
    try:
        media = cl.photo_upload(IMAGE_PATH, CAPTION)
        print(f"SUCCESS! Posted media ID: {media.id}", file=sys.stderr)
        print(f"Post URL: https://www.instagram.com/p/{media.code}/", file=sys.stderr)
        # Print to stdout for easy capture
        print(f"POSTED: https://www.instagram.com/p/{media.code}/")
    except Exception as e:
        print(f"Photo upload failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
