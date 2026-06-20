# 🤖 Instagram Control MCP Server

<div align="center">

[![PyPI version](https://img.shields.io/pypi/v/instagram-mcp-server.svg?color=orange&style=flat-square)](https://pypi.org/project/instagram-mcp-server/)
[![GitHub Release](https://img.shields.io/github/v/release/official-Arvind/instagram-mcp?color=blue&style=flat-square)](https://github.com/official-Arvind/instagram-mcp/releases)
[![License](https://img.shields.io/github/license/official-Arvind/instagram-mcp?style=flat-square)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple?style=flat-square)](https://modelcontextprotocol.io)

**A professional, full-fidelity Model Context Protocol (MCP) server enabling AI agents (like Claude Desktop, Cursor, and custom wrappers) to fully control and manage an Instagram account exactly like a human user.**

[Key Features](#-key-features) • [Installation](#-installation) • [Client Config](#%EF%B8%8F-client-configuration) • [Authentication](#-authentication-flow) • [Tool Reference](#-tool-reference) • [Safety Guide](#-rate-limits--safety)

</div>

---

## ⚡ Overview

The **Instagram Control MCP Server** bridges LLMs with the private Instagram Mobile API. By wrapping `instagrapi` and utilizing `FastMCP`, this integration gives AI agents a set of **68 granular tools** to perform everything from media publishing and direct messaging to relationship management, story uploads, and hashtag explorations.

Unlike simple graph API wrappers, this server works with standard consumer accounts, automatically handles **session persistence**, supports **two-factor authentication (2FA)**, and resolves SMS/email challenge prompts interactively.

---

## 🛠️ Key Features

* 📦 **Production Ready** — Install directly via `pip` or run locally.
* 🔐 **Seamless Auth** — Session cookies, username/password, 2FA, and SMS/Email verification challenge handlers.
* 🚀 **Automatic Persistence** — Saves sessions locally to bypass repeat logins and prevent login flags.
* 📸 **Rich Media Posting** — Support for single-photo posts, carousel albums, video feeds, and Reels.
* 📖 **Interactive Stories** — Upload photos/videos directly to stories.
* 💬 **Frictionless Direct Messages** — Read threads, mark as seen, and send text, photo, or video messages.
* 👥 **Social & Engagement** — Bulletproof interactions: like, unlike, comment, follow, unfollow, block, and list followers.
* 🔍 **Context Discovery** — Search users, tags, locations, highlights, and similar profiles.

---

## 🚀 Installation

You can run this server either as a global package from **PyPI** or clone it for local modifications.

### Option A: Install from PyPI (Recommended)

Installs the package and registers a global CLI entry point `instagram-mcp`:

```bash
pip install instagram-mcp-server
```

### Option B: Local Setup (Development)

Clone the repository, create a virtual environment, and install dependencies:

```bash
git clone https://github.com/official-Arvind/instagram-mcp.git
cd instagram-mcp
python -m venv venv

# Windows
venv\Scripts\pip install -e .

# Mac/Linux
venv/bin/pip install -e .
```

---

## ⚙️ Client Configuration

Configure your favorite MCP host to locate the executable.

### 1. Claude Desktop
Add the following to your `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "instagram-control": {
      "command": "instagram-mcp"
    }
  }
}
```

*If using a virtual environment manually, specify the absolute path to the executable:*
```json
{
  "mcpServers": {
    "instagram-control": {
      "command": "C:\\path\\to\\instagram-mcp\\venv\\Scripts\\instagram-mcp.exe"
    }
  }
}
```

### 2. Cursor IDE
1. Open **Settings** → **Features** → **MCP**.
2. Click **+ Add New MCP Server**.
3. Fill in the parameters:
   * **Name**: `instagram-control`
   * **Type**: `command`
   * **Command**: `instagram-mcp` *(or path to your virtual environment's executable)*

---

## 🔐 Authentication Flow

To allow your AI agent to operate your account, use one of the following methods.

### Method 1: Session Cookie (Recommended & Safest)
Bypasses credential inputs, avoids triggering 2FA blocks, and mimics your existing browser session.

1. Log in to Instagram on your desktop browser.
2. Open **Developer Tools (F12)** → Go to **Application** (Chrome) or **Storage** (Firefox) → **Cookies**.
3. Select `https://www.instagram.com` and copy the value of the `sessionid` cookie.
4. Instruct your agent:
   > *"Log in using session ID with username 'your_username' and session id 'copied_cookie_value'"*

### Method 2: Username & Password
If session cookies are not used, prompt the agent with your credentials:
```
instagram_login_with_credentials(username="your_username", password="your_password")
```
* **Two-Factor Auth**: If the login request triggers 2FA, the agent will receive a challenge response. Provide the code:
  `instagram_complete_2fa(code="123456")`
* **Security Verification**: If Instagram sends a challenge check (Email/SMS verification), provide the code:
  `instagram_complete_challenge(code="123456")`

### Session Lifecycle
On successful authentication, the server saves encrypted session cookies in `instagram_session.json` in the current directory. Subsequent runs will automatically recover this session without prompting for login.

---

## 📂 Tool Reference

The server exposes **68 specialized tools**. Here is the functional breakdown:

<details>
<summary><b>🔐 Authentication & Sessions</b></summary>

* `instagram_login_with_sessionid` — Authenticate via browser cookie session bypass.
* `instagram_login_with_credentials` — Authenticate using username + password.
* `instagram_complete_2fa` — Submit a 2-factor authentication code.
* `instagram_complete_challenge` — Submit SMS/Email challenge verification code.
* `instagram_get_login_status` — Query the state of the session lifecycle.
* `instagram_logout` — Clear local session data and disconnect.

</details>

<details>
<summary><b>📸 Media Posting & Content Management</b></summary>

* `instagram_post_photo` — Upload a single image (supports captions, tags, and locations).
* `instagram_post_album` — Upload carousel posts (up to 10 images).
* `instagram_post_video` — Upload standard video content.
* `instagram_post_reel` — Publish Reels (with custom thumbnails and cover pages).
* `instagram_delete_post` — Delete feed items by Media PK.
* `instagram_get_user_feed` — Retrieve published posts for any profile.
* `instagram_get_timeline_feed` — Fetch the home feed timeline.
* `instagram_get_media_info` — View exact JSON metadata for any post.
* `instagram_download_post` — Save media items directly to disk.

</details>

<details>
<summary><b>📖 Stories & Highlights</b></summary>

* `instagram_post_photo_story` — Publish a photo story (supports link/hashtag stickers).
* `instagram_post_video_story` — Publish a video story (supports link/hashtag stickers).
* `instagram_get_user_stories` — Fetch active stories on any target account.
* `instagram_delete_story` — Remove active stories.
* `instagram_get_story_viewers` — Fetch list of story viewers.
* `instagram_get_highlights` — Fetch highlight categories on a profile.
* `instagram_create_highlight` — Bundle selected active stories into a new highlight.
* `instagram_delete_highlight` — Remove custom highlights.

</details>

<details>
<summary><b>💬 Direct Messaging</b></summary>

* `instagram_get_direct_threads` — Fetch ongoing chat threads and inbox lists.
* `instagram_get_direct_messages` — Retrieve history/chat logs from a thread.
* `instagram_send_direct_message` — Dispatch text DMs.
* `instagram_send_dm_photo` — Send photo attachments inside a thread.
* `instagram_send_dm_video` — Send video attachments inside a thread.
* `instagram_mark_thread_seen` — Mark incoming messages as read.

</details>

<details>
<summary><b>❤️ Social Engagement</b></summary>

* `instagram_like_post` / `instagram_unlike_post` — Toggle likes on feed items.
* `instagram_save_post` / `instagram_unsave_post` — Toggle bookmarking.
* `instagram_comment_on_post` — Post a new comment.
* `instagram_reply_to_comment` — Thread replies under a comment ID.
* `instagram_delete_comment` — Delete comment instances.
* `instagram_like_comment` — Like comment targets.
* `instagram_get_post_comments` — List comments under a post.

</details>

<details>
<summary><b>👥 Profile & Relationships</b></summary>

* `instagram_get_profile` — Fetch metadata of any profile.
* `instagram_edit_profile` — Modify name, bio, and external links.
* `instagram_change_profile_picture` — Update profile photo.
* `instagram_follow_user` / `instagram_unfollow_user` — Toggle follow states.
* `instagram_get_followers` / `instagram_get_following` — Query social graphs.
* `instagram_block_user` / `instagram_unblock_user` — Manage blocklists.
* `instagram_get_blocked_users` — View current blocks.
* `instagram_get_notifications` — Read current activity notifications (likes, tags, comments).
* `instagram_get_pending_follow_requests` — List incoming follow requests.

</details>

---

## ⚠️ Rate Limits & Safety

Because this server connects using the private mobile client layer, it is subject to Instagram's rate limit filters. **To prevent account suspension or temporary blocks, adhere to these guidelines:**

1. **Avoid High-Frequency Actions** — Spread out posting, liking, and messaging. Do not script loops that execute multiple social actions in rapid succession.
2. **Mimic Human Timing** — If scripting routines, inject random delays (`time.sleep(20, 60)`) between events.
3. **Warm-Up New Accounts** — Freshly created profiles are flags for automation blocks. Use an established account or warm up a new account gradually.
4. **Use Cookie Sessions** — Cookie login triggers far fewer security flags than standard username/password authentication.

---

## 🛡️ Disclaimer

This software is for educational purposes only. It interacts with Instagram's private APIs and is **not** endorsed, affiliated with, or supported by Meta Platforms Inc. Continued automation may result in temporary limits, shadowbans, or permanent closure of your account. Use responsibly at your own risk.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more details.
