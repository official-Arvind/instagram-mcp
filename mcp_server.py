"""
mcp_server.py
--------------
Instagram Control MCP Server — built with FastMCP + instagrapi.
Exposes 50+ tools covering every Instagram action a human can perform,
and then some.

Authentication → Profile → Feed → Reels → Stories → Highlights
→ Comments → Likes → Saves → DMs → Search → Hashtags
→ Following/Followers → Notifications → Analytics → Media Downloads
"""

import os
import sys
import time
import random
import tempfile
import requests
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastmcp import FastMCP
from instagram_client import InstagramClientWrapper

# ─────────────────────────────────────────────────────────────────────────────
# SERVER & CLIENT SETUP
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "Instagram Control",
    instructions=(
        "This server lets AI agents fully control an Instagram account. "
        "Always call instagram_get_login_status first to verify authentication. "
        "Use instagram_login_with_sessionid for the most stable authentication. "
        "A session file is persisted locally and auto-loaded between runs."
    )
)

_SESSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_session.json")
ig = InstagramClientWrapper(session_path=_SESSION_PATH)

# Attempt to auto-restore session on startup
ig.init_from_saved_session()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _require_login() -> Optional[str]:
    """Returns an error string if not logged in, else None."""
    if not ig.is_logged_in():
        return "Error: Not logged in. Call instagram_login_with_sessionid or instagram_login_with_credentials first."
    return None

def _download_if_url(path_or_url: str, suffix: str = ".jpg") -> str:
    """Downloads a file from a URL and returns the local temp path."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        r = requests.get(path_or_url, stream=True, timeout=30)
        r.raise_for_status()
        # Try to detect extension from Content-Type
        ct = r.headers.get("Content-Type", "")
        if "mp4" in ct or "video" in ct:
            suffix = ".mp4"
        elif "jpeg" in ct or "jpg" in ct:
            suffix = ".jpg"
        elif "png" in ct:
            suffix = ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        for chunk in r.iter_content(8192):
            tmp.write(chunk)
        tmp.close()
        return tmp.name
    return path_or_url

def _cleanup(local: str, original: str):
    """Removes temp file if we downloaded it."""
    if original.startswith("http://") or original.startswith("https://"):
        try:
            if os.path.exists(local):
                os.remove(local)
        except Exception:
            pass

def _fmt_user(u) -> dict:
    return {
        "pk": str(u.pk),
        "username": u.username,
        "full_name": u.full_name,
        "is_private": u.is_private,
        "is_verified": u.is_verified,
    }

def _fmt_media(m) -> dict:
    return {
        "id": str(m.pk),
        "code": m.code,
        "url": f"https://www.instagram.com/p/{m.code}/",
        "type": m.media_type,
        "caption": m.caption_text[:200] if m.caption_text else "",
        "like_count": m.like_count,
        "comment_count": m.comment_count,
        "taken_at": str(m.taken_at),
        "user": m.user.username if m.user else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTHENTICATION TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_login_with_credentials(username: str, password: str) -> str:
    """
    Log in to Instagram using username and password.
    If 2FA is enabled, returns status 'needs_2fa' — follow up with instagram_complete_2fa.
    If a security challenge triggers, returns 'needs_challenge' — follow up with instagram_complete_challenge.
    """
    return str(ig.login_with_credentials(username, password))


@mcp.tool()
def instagram_login_with_sessionid(username: str, session_id: str) -> str:
    """
    Log in using a browser sessionid cookie (most reliable method — bypasses 2FA).
    How to get the sessionid: Open Instagram in browser → F12 DevTools →
    Application/Storage → Cookies → instagram.com → copy the 'sessionid' value.
    """
    return str(ig.login_with_sessionid(username, session_id))


@mcp.tool()
def instagram_complete_2fa(code: str) -> str:
    """Submit the 2FA authenticator app code after login returned 'needs_2fa'."""
    return str(ig.complete_2fa(code))


@mcp.tool()
def instagram_complete_challenge(code: str) -> str:
    """Submit the email/SMS challenge verification code after login returned 'needs_challenge'."""
    return str(ig.complete_challenge(code))


@mcp.tool()
def instagram_get_login_status() -> str:
    """Check if the server is authenticated and which account is active."""
    return str(ig.get_login_status())


@mcp.tool()
def instagram_logout() -> str:
    """Log out of Instagram and delete the saved session file from disk."""
    return str(ig.logout())


# ─────────────────────────────────────────────────────────────────────────────
# 2. PROFILE TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_profile(username: Optional[str] = None) -> str:
    """
    Get full profile information for the logged-in account, or any target username.
    Returns follower/following counts, bio, posts count, website, etc.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        u = ig.cl.user_info_by_username(target)
        return str({
            "pk": str(u.pk),
            "username": u.username,
            "full_name": u.full_name,
            "biography": u.biography,
            "external_url": str(u.external_url) if u.external_url else None,
            "follower_count": u.follower_count,
            "following_count": u.following_count,
            "media_count": u.media_count,
            "is_private": u.is_private,
            "is_verified": u.is_verified,
            "is_business": u.is_business,
            "account_type": u.account_type,
            "profile_pic_url": str(u.profile_pic_url),
            "category": u.category,
        })
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_edit_profile(full_name: Optional[str] = None, biography: Optional[str] = None,
                             external_url: Optional[str] = None) -> str:
    """
    Edit the logged-in account's profile. Provide any combination of:
    full_name, biography (bio text), external_url (website link).
    Only provided fields are updated.
    """
    if err := _require_login(): return err
    try:
        # Fetch current values so we only override what's requested
        u = ig.cl.user_info(ig.cl.user_id)
        result = ig.cl.account_edit(
            full_name=full_name or u.full_name,
            biography=biography if biography is not None else u.biography,
            external_url=external_url or str(u.external_url or ""),
        )
        return f"Profile updated successfully. Result: {result}"
    except Exception as e:
        return f"Error updating profile: {e}"


@mcp.tool()
def instagram_change_profile_picture(image_path_or_url: str) -> str:
    """
    Change the profile picture. Accepts a local file path or a direct image URL.
    """
    if err := _require_login(): return err
    local = None
    try:
        local = _download_if_url(image_path_or_url, ".jpg")
        result = ig.cl.account_change_picture(local)
        return f"Profile picture changed successfully."
    except Exception as e:
        return f"Error changing profile picture: {e}"
    finally:
        if local:
            _cleanup(local, image_path_or_url)


# ─────────────────────────────────────────────────────────────────────────────
# 3. FEED / MEDIA TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_post_photo(image_path_or_url: str, caption: str,
                          location_name: Optional[str] = None) -> str:
    """
    Post a photo to the Instagram feed. Accepts local file path or direct image URL.
    Optionally include a location name to tag the post.
    """
    if err := _require_login(): return err
    local = None
    try:
        local = _download_if_url(image_path_or_url, ".jpg")
        location = None
        if location_name:
            results = ig.cl.location_search(location_name)
            if results:
                location = results[0]
        media = ig.cl.photo_upload(local, caption, location=location)
        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/p/{media.code}/",
            "caption": media.caption_text[:100] if media.caption_text else "",
        })
    except Exception as e:
        return f"Error posting photo: {e}"
    finally:
        if local:
            _cleanup(local, image_path_or_url)


@mcp.tool()
def instagram_post_album(image_paths_or_urls: List[str], caption: str) -> str:
    """
    Post multiple photos/videos as a carousel album (up to 10 items).
    Accepts a list of local paths or URLs.
    """
    if err := _require_login(): return err
    locals_ = []
    try:
        from pathlib import Path as _P
        paths = []
        for item in image_paths_or_urls[:10]:
            local = _download_if_url(item, ".jpg")
            locals_.append((local, item))
            paths.append(_P(local))
        media = ig.cl.album_upload(paths, caption)
        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/p/{media.code}/",
            "items_count": len(paths),
        })
    except Exception as e:
        return f"Error posting album: {e}"
    finally:
        for local, orig in locals_:
            _cleanup(local, orig)


@mcp.tool()
def instagram_post_video(video_path_or_url: str, caption: str,
                          thumbnail_path_or_url: Optional[str] = None) -> str:
    """
    Post a video to the Instagram feed. Accepts local path or URL.
    Optionally provide a thumbnail image path or URL.
    """
    if err := _require_login(): return err
    local_v = None
    local_t = None
    try:
        local_v = _download_if_url(video_path_or_url, ".mp4")
        if thumbnail_path_or_url:
            local_t = _download_if_url(thumbnail_path_or_url, ".jpg")
        media = ig.cl.video_upload(local_v, caption, thumbnail=local_t)
        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/p/{media.code}/",
        })
    except Exception as e:
        return f"Error posting video: {e}"
    finally:
        if local_v: _cleanup(local_v, video_path_or_url)
        if local_t and thumbnail_path_or_url: _cleanup(local_t, thumbnail_path_or_url)


@mcp.tool()
def instagram_post_reel(video_path_or_url: str, caption: str) -> str:
    """
    Post a video as a Reel. Accepts local path or URL.
    Reels get significantly more reach than regular feed videos.
    """
    if err := _require_login(): return err
    local_v = None
    try:
        local_v = _download_if_url(video_path_or_url, ".mp4")
        media = ig.cl.clip_upload(local_v, caption)
        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/reel/{media.code}/",
        })
    except Exception as e:
        return f"Error posting reel: {e}"
    finally:
        if local_v: _cleanup(local_v, video_path_or_url)


@mcp.tool()
def instagram_delete_post(media_id: str) -> str:
    """
    Delete a post by its media ID. This is permanent and cannot be undone.
    """
    if err := _require_login(): return err
    try:
        result = ig.cl.media_delete(media_id)
        return f"Post {media_id} deleted successfully. Result: {result}"
    except Exception as e:
        return f"Error deleting post: {e}"


@mcp.tool()
def instagram_get_user_feed(username: Optional[str] = None, amount: int = 12) -> str:
    """
    Get recent posts from the logged-in account or a target username.
    Returns post URLs, captions, like/comment counts, and timestamps.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        user_id = ig.cl.user_id_from_username(target)
        medias = ig.cl.user_medias(user_id, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error fetching feed: {e}"


@mcp.tool()
def instagram_get_timeline_feed(amount: int = 10) -> str:
    """
    Get the home timeline feed (posts from accounts you follow),
    just like opening the Instagram app to the main feed.
    """
    if err := _require_login(): return err
    try:
        feed = ig.cl.get_timeline_feed()
        items = feed.get("feed_items", [])
        results = []
        count = 0
        for item in items:
            if count >= amount:
                break
            mi = item.get("media_or_ad")
            if mi:
                code = mi.get("code", "")
                caption_data = mi.get("caption") or {}
                results.append({
                    "code": code,
                    "url": f"https://www.instagram.com/p/{code}/",
                    "user": mi.get("user", {}).get("username", ""),
                    "caption": (caption_data.get("text", "") or "")[:200],
                    "like_count": mi.get("like_count", 0),
                    "comment_count": mi.get("comment_count", 0),
                })
                count += 1
        return str(results)
    except Exception as e:
        return f"Error fetching timeline: {e}"


@mcp.tool()
def instagram_get_media_info(media_id_or_url: str) -> str:
    """
    Get detailed information about a post by its media ID or Instagram post URL.
    """
    if err := _require_login(): return err
    try:
        # Try extracting code from URL
        if "instagram.com" in media_id_or_url:
            match = re.search(r'/p/([A-Za-z0-9_-]+)/', media_id_or_url)
            if match:
                code = match.group(1)
                media_id_or_url = ig.cl.media_id(code)
        m = ig.cl.media_info(media_id_or_url)
        return str(_fmt_media(m))
    except Exception as e:
        return f"Error fetching media info: {e}"


@mcp.tool()
def instagram_download_post(media_id_or_url: str, save_dir: Optional[str] = None) -> str:
    """
    Download a post's media (photo/video) to local disk.
    Saves to the specified directory, or to 'downloads/' in the project folder.
    """
    if err := _require_login(): return err
    try:
        if "instagram.com" in media_id_or_url:
            match = re.search(r'/p/([A-Za-z0-9_-]+)/', media_id_or_url)
            if match:
                code = match.group(1)
                media_id_or_url = ig.cl.media_id(code)

        dest = save_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        os.makedirs(dest, exist_ok=True)

        m = ig.cl.media_info(media_id_or_url)
        if m.media_type == 1:  # Photo
            path = ig.cl.photo_download(media_id_or_url, folder=dest)
        elif m.media_type == 2:  # Video
            path = ig.cl.video_download(media_id_or_url, folder=dest)
        else:
            path = ig.cl.photo_download(media_id_or_url, folder=dest)

        return f"Downloaded to: {path}"
    except Exception as e:
        return f"Error downloading media: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. STORIES
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_post_photo_story(image_path_or_url: str) -> str:
    """Post a photo to your Story. Accepts local path or image URL."""
    if err := _require_login(): return err
    local = None
    try:
        local = _download_if_url(image_path_or_url, ".jpg")
        m = ig.cl.photo_upload_to_story(local)
        return f"Story posted. Media ID: {m.pk}"
    except Exception as e:
        return f"Error posting story: {e}"
    finally:
        if local: _cleanup(local, image_path_or_url)


@mcp.tool()
def instagram_post_video_story(video_path_or_url: str) -> str:
    """Post a video to your Story. Accepts local path or video URL."""
    if err := _require_login(): return err
    local = None
    try:
        local = _download_if_url(video_path_or_url, ".mp4")
        m = ig.cl.video_upload_to_story(local)
        return f"Video story posted. Media ID: {m.pk}"
    except Exception as e:
        return f"Error posting video story: {e}"
    finally:
        if local: _cleanup(local, video_path_or_url)


@mcp.tool()
def instagram_get_user_stories(username: Optional[str] = None) -> str:
    """
    Get active stories for the logged-in account or a target username.
    Returns story media IDs, types, and timestamps.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        user_id = ig.cl.user_id_from_username(target)
        stories = ig.cl.user_stories(user_id)
        return str([{
            "pk": str(s.pk),
            "media_type": s.media_type,
            "taken_at": str(s.taken_at),
            "expiring_at": str(s.expiring_at) if hasattr(s, 'expiring_at') else None,
        } for s in stories])
    except Exception as e:
        return f"Error fetching stories: {e}"


@mcp.tool()
def instagram_delete_story(story_id: str) -> str:
    """Delete one of your active stories by its media ID."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_delete(story_id)
        return f"Story {story_id} deleted. Result: {result}"
    except Exception as e:
        return f"Error deleting story: {e}"


@mcp.tool()
def instagram_get_story_viewers(story_id: str) -> str:
    """
    Get the list of users who viewed one of your stories.
    Returns usernames and user IDs.
    """
    if err := _require_login(): return err
    try:
        viewers = ig.cl.story_viewers(story_id)
        return str([_fmt_user(v) for v in viewers])
    except Exception as e:
        return f"Error fetching story viewers: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. HIGHLIGHTS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_highlights(username: Optional[str] = None) -> str:
    """
    Get story highlights for the logged-in account or a target username.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        user_id = ig.cl.user_id_from_username(target)
        highlights = ig.cl.highlights(user_id)
        return str([{
            "pk": str(h.pk),
            "title": h.title,
            "media_count": h.media_count,
            "cover_url": str(h.cover_url) if hasattr(h, 'cover_url') else None,
        } for h in highlights])
    except Exception as e:
        return f"Error fetching highlights: {e}"


@mcp.tool()
def instagram_create_highlight(title: str, story_ids: List[str]) -> str:
    """
    Create a new highlight from existing stories.
    Provide the highlight title and a list of story media IDs to include.
    """
    if err := _require_login(): return err
    try:
        h = ig.cl.highlight_create(title, story_ids)
        return f"Highlight '{title}' created. ID: {h.pk}"
    except Exception as e:
        return f"Error creating highlight: {e}"


@mcp.tool()
def instagram_delete_highlight(highlight_id: str) -> str:
    """Delete a highlights collection by its ID."""
    if err := _require_login(): return err
    try:
        result = ig.cl.highlight_delete(highlight_id)
        return f"Highlight {highlight_id} deleted. Result: {result}"
    except Exception as e:
        return f"Error deleting highlight: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. ENGAGEMENT — LIKES, COMMENTS, SAVES
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_like_post(media_id: str) -> str:
    """Like a post by its media ID."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_like(media_id)
        return f"Liked post {media_id}. Result: {result}"
    except Exception as e:
        return f"Error liking post: {e}"


@mcp.tool()
def instagram_unlike_post(media_id: str) -> str:
    """Unlike (remove like from) a post by its media ID."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_unlike(media_id)
        return f"Unliked post {media_id}. Result: {result}"
    except Exception as e:
        return f"Error unliking post: {e}"


@mcp.tool()
def instagram_save_post(media_id: str) -> str:
    """Save a post to your Saved collection."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_save(media_id)
        return f"Post {media_id} saved. Result: {result}"
    except Exception as e:
        return f"Error saving post: {e}"


@mcp.tool()
def instagram_unsave_post(media_id: str) -> str:
    """Remove a post from your Saved collection."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_unsave(media_id)
        return f"Post {media_id} unsaved. Result: {result}"
    except Exception as e:
        return f"Error unsaving post: {e}"


@mcp.tool()
def instagram_get_post_likers(media_id: str) -> str:
    """Get the list of users who liked a post."""
    if err := _require_login(): return err
    try:
        likers = ig.cl.media_likers(media_id)
        return str([_fmt_user(u) for u in likers])
    except Exception as e:
        return f"Error fetching likers: {e}"


@mcp.tool()
def instagram_comment_on_post(media_id: str, text: str) -> str:
    """Post a comment on a media item."""
    if err := _require_login(): return err
    try:
        c = ig.cl.media_comment(media_id, text)
        return f"Comment posted. ID: {c.pk}, Text: '{c.text}'"
    except Exception as e:
        return f"Error posting comment: {e}"


@mcp.tool()
def instagram_reply_to_comment(media_id: str, comment_id: str, text: str) -> str:
    """
    Reply to a specific comment on a post.
    """
    if err := _require_login(): return err
    try:
        c = ig.cl.media_comment(media_id, text, replied_to_comment_id=int(comment_id))
        return f"Reply posted. ID: {c.pk}, Text: '{c.text}'"
    except Exception as e:
        return f"Error replying to comment: {e}"


@mcp.tool()
def instagram_delete_comment(media_id: str, comment_id: str) -> str:
    """Delete a comment (yours or on your post) by media ID and comment ID."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_comment_delete(media_id, comment_id)
        return f"Comment {comment_id} deleted. Result: {result}"
    except Exception as e:
        return f"Error deleting comment: {e}"


@mcp.tool()
def instagram_like_comment(media_id: str, comment_id: str) -> str:
    """Like a comment on a post."""
    if err := _require_login(): return err
    try:
        result = ig.cl.media_comment_like(comment_id)
        return f"Comment {comment_id} liked. Result: {result}"
    except Exception as e:
        return f"Error liking comment: {e}"


@mcp.tool()
def instagram_get_post_comments(media_id: str, amount: int = 20) -> str:
    """Get comments on a post. Returns commenter usernames, text, and timestamps."""
    if err := _require_login(): return err
    try:
        comments = ig.cl.media_comments(media_id, amount)
        return str([{
            "pk": str(c.pk),
            "user": c.user.username,
            "text": c.text,
            "like_count": c.like_count,
            "created_at": str(c.created_at_utc),
        } for c in comments])
    except Exception as e:
        return f"Error fetching comments: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. FOLLOWING & FOLLOWERS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_follow_user(username: str) -> str:
    """Follow a user by their username."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        result = ig.cl.user_follow(uid)
        return f"Followed @{username}. Result: {result}"
    except Exception as e:
        return f"Error following user: {e}"


@mcp.tool()
def instagram_unfollow_user(username: str) -> str:
    """Unfollow a user by their username."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        result = ig.cl.user_unfollow(uid)
        return f"Unfollowed @{username}. Result: {result}"
    except Exception as e:
        return f"Error unfollowing user: {e}"


@mcp.tool()
def instagram_get_followers(username: Optional[str] = None, amount: int = 50) -> str:
    """
    Get the followers list for the logged-in account or a target username.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        followers = ig.cl.user_followers(uid, amount=amount)
        return str([_fmt_user(u) for u in followers.values()])
    except Exception as e:
        return f"Error fetching followers: {e}"


@mcp.tool()
def instagram_get_following(username: Optional[str] = None, amount: int = 50) -> str:
    """
    Get the list of accounts that the logged-in account (or a target username) is following.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        following = ig.cl.user_following(uid, amount=amount)
        return str([_fmt_user(u) for u in following.values()])
    except Exception as e:
        return f"Error fetching following: {e}"


@mcp.tool()
def instagram_block_user(username: str) -> str:
    """Block a user by their username."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        result = ig.cl.user_block(uid)
        return f"Blocked @{username}. Result: {result}"
    except Exception as e:
        return f"Error blocking user: {e}"


@mcp.tool()
def instagram_unblock_user(username: str) -> str:
    """Unblock a previously blocked user."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        result = ig.cl.user_unblock(uid)
        return f"Unblocked @{username}. Result: {result}"
    except Exception as e:
        return f"Error unblocking user: {e}"


@mcp.tool()
def instagram_get_blocked_users() -> str:
    """Get the full list of users you have blocked."""
    if err := _require_login(): return err
    try:
        blocked = ig.cl.user_blocked_list()
        return str([_fmt_user(u) for u in blocked])
    except Exception as e:
        return f"Error fetching blocked users: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. DIRECT MESSAGES (DMs)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_direct_threads(amount: int = 20) -> str:
    """
    Get recent DM threads. Returns thread IDs, participants, and last activity time.
    """
    if err := _require_login(): return err
    try:
        threads = ig.cl.direct_threads(amount)
        return str([{
            "thread_id": t.id,
            "title": t.thread_title or "",
            "participants": [u.username for u in (t.users or [])],
            "last_activity_at": str(t.last_activity_at),
            "unread_count": t.read_state,
            "muted": t.muted,
        } for t in threads])
    except Exception as e:
        return f"Error fetching threads: {e}"


@mcp.tool()
def instagram_get_direct_messages(thread_id: str, amount: int = 30) -> str:
    """Get messages from a specific DM thread."""
    if err := _require_login(): return err
    try:
        thread = ig.cl.direct_thread(thread_id)
        msgs = sorted(thread.messages, key=lambda m: m.timestamp)[-amount:]
        return str([{
            "id": m.id,
            "user_id": str(m.user_id),
            "type": m.item_type,
            "text": m.text,
            "timestamp": str(m.timestamp),
        } for m in msgs])
    except Exception as e:
        return f"Error fetching messages: {e}"


@mcp.tool()
def instagram_send_direct_message(text: str, username: Optional[str] = None,
                                   thread_id: Optional[str] = None) -> str:
    """
    Send a text DM. Specify either:
    - username: to start a new conversation or message a user.
    - thread_id: to reply to an existing conversation thread.
    """
    if err := _require_login(): return err
    if not username and not thread_id:
        return "Error: Provide either username or thread_id."
    try:
        if thread_id:
            msg = ig.cl.direct_send(text, thread_ids=[thread_id])
        else:
            uid = ig.cl.user_id_from_username(username)
            msg = ig.cl.direct_send(text, user_ids=[uid])
        return f"Message sent. ID: {msg.id}"
    except Exception as e:
        return f"Error sending message: {e}"


@mcp.tool()
def instagram_send_dm_photo(image_path_or_url: str, username: Optional[str] = None,
                             thread_id: Optional[str] = None) -> str:
    """Send a photo via Direct Message. Specify username or thread_id."""
    if err := _require_login(): return err
    if not username and not thread_id:
        return "Error: Provide either username or thread_id."
    local = None
    try:
        local = _download_if_url(image_path_or_url, ".jpg")
        if thread_id:
            msg = ig.cl.direct_send_photo(local, thread_ids=[thread_id])
        else:
            uid = ig.cl.user_id_from_username(username)
            msg = ig.cl.direct_send_photo(local, user_ids=[uid])
        return f"Photo DM sent. ID: {msg.id}"
    except Exception as e:
        return f"Error sending photo DM: {e}"
    finally:
        if local: _cleanup(local, image_path_or_url)


@mcp.tool()
def instagram_send_dm_video(video_path_or_url: str, username: Optional[str] = None,
                             thread_id: Optional[str] = None) -> str:
    """Send a video via Direct Message. Specify username or thread_id."""
    if err := _require_login(): return err
    if not username and not thread_id:
        return "Error: Provide either username or thread_id."
    local = None
    try:
        local = _download_if_url(video_path_or_url, ".mp4")
        if thread_id:
            msg = ig.cl.direct_send_video(local, thread_ids=[thread_id])
        else:
            uid = ig.cl.user_id_from_username(username)
            msg = ig.cl.direct_send_video(local, user_ids=[uid])
        return f"Video DM sent. ID: {msg.id}"
    except Exception as e:
        return f"Error sending video DM: {e}"
    finally:
        if local: _cleanup(local, video_path_or_url)


@mcp.tool()
def instagram_mark_thread_seen(thread_id: str) -> str:
    """Mark a DM thread as seen/read."""
    if err := _require_login(): return err
    try:
        ig.cl.direct_send_seen(thread_id)
        return f"Thread {thread_id} marked as seen."
    except Exception as e:
        return f"Error marking thread seen: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 9. SEARCH & EXPLORE
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_search_users(query: str, count: int = 10) -> str:
    """
    Search for Instagram users by name or username.
    Returns matching accounts with follower counts.
    """
    if err := _require_login(): return err
    try:
        results = ig.cl.search_users(query)[:count]
        return str([_fmt_user(u) for u in results])
    except Exception as e:
        return f"Error searching users: {e}"


@mcp.tool()
def instagram_search_hashtag(hashtag: str, amount: int = 12) -> str:
    """
    Search posts by hashtag. Returns recent posts tagged with the given hashtag.
    Do not include the '#' symbol in the hashtag parameter.
    """
    if err := _require_login(): return err
    try:
        medias = ig.cl.hashtag_medias_recent(hashtag, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error searching hashtag: {e}"


@mcp.tool()
def instagram_get_hashtag_top_posts(hashtag: str, amount: int = 9) -> str:
    """
    Get the top/trending posts for a given hashtag.
    Do not include the '#' symbol.
    """
    if err := _require_login(): return err
    try:
        medias = ig.cl.hashtag_medias_top(hashtag, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error fetching hashtag top posts: {e}"


@mcp.tool()
def instagram_get_hashtag_info(hashtag: str) -> str:
    """
    Get information about a hashtag including post count.
    """
    if err := _require_login(): return err
    try:
        info = ig.cl.hashtag_info(hashtag)
        return str({
            "name": info.name,
            "media_count": info.media_count,
            "id": str(info.id),
        })
    except Exception as e:
        return f"Error fetching hashtag info: {e}"


@mcp.tool()
def instagram_get_similar_accounts(username: str) -> str:
    """
    Get accounts similar to a given username (Instagram's 'suggested for you' logic).
    Useful for finding related accounts in a niche.
    """
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        similar = ig.cl.user_related_profiles(uid)
        return str([_fmt_user(u) for u in similar])
    except Exception as e:
        return f"Error fetching similar accounts: {e}"


@mcp.tool()
def instagram_get_location_posts(location_name: str, amount: int = 12) -> str:
    """
    Get recent posts tagged at a specific location by name.
    """
    if err := _require_login(): return err
    try:
        results = ig.cl.location_search(location_name)
        if not results:
            return f"No location found for '{location_name}'"
        loc = results[0]
        medias = ig.cl.location_medias_recent(loc.pk, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error fetching location posts: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 10. NOTIFICATIONS & ACTIVITY
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_notifications(amount: int = 20) -> str:
    """
    Get recent activity notifications — likes, comments, follows, mentions, etc.
    """
    if err := _require_login(): return err
    try:
        activity = ig.cl.news_inbox_v1()
        counts = activity.get("counts", {})
        stories = activity.get("new_stories", [])[:amount]
        items = []
        for s in stories:
            args = s.get("args", {})
            items.append({
                "type": s.get("type"),
                "text": args.get("text", ""),
                "timestamp": args.get("timestamp"),
                "profile_id": args.get("profile_id"),
                "profile_name": args.get("profile_name"),
            })
        return str({"unread_counts": counts, "notifications": items})
    except Exception as e:
        return f"Error fetching notifications: {e}"


@mcp.tool()
def instagram_get_pending_follow_requests() -> str:
    """
    Get pending follow requests for a private account.
    Returns list of users waiting for approval.
    """
    if err := _require_login(): return err
    try:
        pending = ig.cl.pending_requests_v1()
        users = pending.get("users", [])
        return str([{
            "pk": str(u.get("pk")),
            "username": u.get("username"),
            "full_name": u.get("full_name"),
        } for u in users])
    except Exception as e:
        return f"Error fetching pending requests: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
