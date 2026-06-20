# 🤖 Instagram Control MCP Server

> **Let any AI agent fully control a real Instagram account — post, DM, follow, comment, search, and more.**

Built with **Python**, **[instagrapi](https://github.com/adw0rd/instagrapi)** (private mobile API), and **[FastMCP](https://github.com/jlowin/fastmcp)**.

---

## ✨ Features — 50+ Tools

### 🔐 Authentication
| Tool | Description |
|------|-------------|
| `instagram_login_with_sessionid` | Login via browser cookie (recommended) |
| `instagram_login_with_credentials` | Login via username + password |
| `instagram_complete_2fa` | Submit 2FA authenticator code |
| `instagram_complete_challenge` | Submit email/SMS challenge code |
| `instagram_get_login_status` | Check active session |
| `instagram_logout` | Logout and clear session |

### 👤 Profile
| Tool | Description |
|------|-------------|
| `instagram_get_profile` | Get profile info (any user) |
| `instagram_edit_profile` | Edit bio, name, website |
| `instagram_change_profile_picture` | Change profile picture |

### 📸 Feed Posting
| Tool | Description |
|------|-------------|
| `instagram_post_photo` | Post a photo with caption + location |
| `instagram_post_album` | Post carousel (up to 10 items) |
| `instagram_post_video` | Post a feed video |
| `instagram_post_reel` | Post a Reel |
| `instagram_delete_post` | Delete a post permanently |
| `instagram_get_user_feed` | Get posts from any user |
| `instagram_get_timeline_feed` | Get your home feed |
| `instagram_get_media_info` | Get details of any post |
| `instagram_download_post` | Download photo/video to disk |

### 📖 Stories
| Tool | Description |
|------|-------------|
| `instagram_post_photo_story` | Post a photo story |
| `instagram_post_video_story` | Post a video story |
| `instagram_get_user_stories` | Get active stories (any user) |
| `instagram_delete_story` | Delete your story |
| `instagram_get_story_viewers` | See who viewed your story |

### 🌟 Highlights
| Tool | Description |
|------|-------------|
| `instagram_get_highlights` | Get highlights of any account |
| `instagram_create_highlight` | Create a new highlight |
| `instagram_delete_highlight` | Delete a highlight |

### ❤️ Engagement
| Tool | Description |
|------|-------------|
| `instagram_like_post` | Like a post |
| `instagram_unlike_post` | Unlike a post |
| `instagram_save_post` | Save a post |
| `instagram_unsave_post` | Unsave a post |
| `instagram_get_post_likers` | See who liked a post |
| `instagram_comment_on_post` | Post a comment |
| `instagram_reply_to_comment` | Reply to a comment |
| `instagram_delete_comment` | Delete a comment |
| `instagram_like_comment` | Like a comment |
| `instagram_get_post_comments` | Get all comments on a post |

### 👥 Following & Relations
| Tool | Description |
|------|-------------|
| `instagram_follow_user` | Follow a user |
| `instagram_unfollow_user` | Unfollow a user |
| `instagram_get_followers` | Get followers list |
| `instagram_get_following` | Get following list |
| `instagram_block_user` | Block a user |
| `instagram_unblock_user` | Unblock a user |
| `instagram_get_blocked_users` | See blocked accounts |

### 💬 Direct Messages
| Tool | Description |
|------|-------------|
| `instagram_get_direct_threads` | Get DM thread list |
| `instagram_get_direct_messages` | Get messages in a thread |
| `instagram_send_direct_message` | Send text DM |
| `instagram_send_dm_photo` | Send photo DM |
| `instagram_send_dm_video` | Send video DM |
| `instagram_mark_thread_seen` | Mark thread as read |

### 🔍 Search & Explore
| Tool | Description |
|------|-------------|
| `instagram_search_users` | Search users by name/username |
| `instagram_search_hashtag` | Get recent posts by hashtag |
| `instagram_get_hashtag_top_posts` | Get top posts by hashtag |
| `instagram_get_hashtag_info` | Get hashtag stats |
| `instagram_get_similar_accounts` | Find similar accounts |
| `instagram_get_location_posts` | Get posts from a location |

### 🔔 Notifications & Activity
| Tool | Description |
|------|-------------|
| `instagram_get_notifications` | Get likes, comments, follows, mentions |
| `instagram_get_pending_follow_requests` | Get pending follow requests |

---

## 🚀 Installation

### 1. Clone this repository
```bash
git clone https://github.com/YOUR_USERNAME/instagram-mcp.git
cd instagram-mcp
```

### 2. Create virtual environment & install dependencies
```bash
python -m venv venv

# Windows
venv\Scripts\pip install -r requirements.txt

# Mac/Linux
venv/bin/pip install -r requirements.txt
```

---

## ⚙️ Integration with AI Clients

### Claude Desktop
Edit `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "instagram-control": {
      "command": "C:\\path\\to\\instagram-mcp\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\instagram-mcp\\mcp_server.py"]
    }
  }
}
```
Restart Claude Desktop. The Instagram tools will appear automatically.

### Cursor IDE
1. Open **Settings** → **Features** → **MCP**
2. Click **+ Add New MCP Server**
3. Set:
   - **Name:** `instagram-control`
   - **Type:** `command`
   - **Command:** `C:\path\to\instagram-mcp\venv\Scripts\python.exe C:\path\to\instagram-mcp\mcp_server.py`

---

## 🔐 Logging In

### Method 1: Session ID (Recommended — No 2FA, Most Stable)
1. Log in to Instagram in your browser (Chrome/Firefox/Edge)
2. Open **DevTools** (F12) → **Application** (Chrome) or **Storage** (Firefox)
3. Navigate to **Cookies** → `https://www.instagram.com`
4. Find and copy the value of the `sessionid` cookie
5. Tell your AI agent:
   > `instagram_login_with_sessionid(username="your_username", session_id="YOUR_COOKIE_VALUE")`

### Method 2: Username & Password
```
instagram_login_with_credentials(username="your_username", password="your_password")
```
- If 2FA is required: call `instagram_complete_2fa(code="123456")`
- If a challenge triggers: call `instagram_complete_challenge(code="123456")`

### Session Persistence
After the first successful login, a `instagram_session.json` file is saved locally.
On the next server start, the session is **automatically restored** — no re-authentication needed.

---

## ⚠️ Disclaimer
This project uses Instagram's unofficial private API (`instagrapi`). Usage violates Instagram's Terms of Service. Use responsibly — do not spam, harass, or automate high-frequency actions. The authors are not responsible for any account suspension or ban resulting from use of this software.

---

## 🛠️ Tech Stack
- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP server framework
- **[instagrapi](https://github.com/adw0rd/instagrapi)** — Instagram private API wrapper
- **[Pillow](https://pillow.readthedocs.io/)** — Image processing
- **[Requests](https://requests.readthedocs.io/)** — HTTP downloads

---

## 📄 License
MIT License — free to use, modify, and distribute.
