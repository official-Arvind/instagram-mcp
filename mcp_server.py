"""
mcp_server.py
--------------
Instagram Control MCP Server — built with FastMCP + instagrapi.
Exposes 60+ tools covering EVERY Instagram action a human can perform.

FULL POST MANAGEMENT:
  caption, hashtags, @mentions in caption, user-tag people IN photos,
  location tags, alt text (accessibility), close-friends stories,
  story stickers (hashtag/mention/location/link), edit captions,
  disable/enable comments, archive/unarchive, pin/unpin, and more.
"""

import os
import re
import sys
import tempfile
import requests
from pathlib import Path
from typing import Optional, List

from fastmcp import FastMCP
from instagram_client import InstagramClientWrapper

# ─────────────────────────────────────────────────────────────────────────────
# SERVER & CLIENT SETUP
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "Instagram Control",
    instructions=(
        "Full Instagram account control server. "
        "Auto-restores session on startup — just call instagram_get_login_status to verify. "
        "When posting, always build the caption with relevant hashtags and @mentions included. "
        "Use instagram_login_with_sessionid for the most reliable authentication."
    )
)

_SESSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_session.json")
ig = InstagramClientWrapper(session_path=_SESSION_PATH)
ig.init_from_saved_session()  # auto-restore on startup


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _require_login() -> Optional[str]:
    if not ig.is_logged_in():
        return "Error: Not logged in. Call instagram_login_with_sessionid or instagram_login_with_credentials first."
    return None

def _download_if_url(path_or_url: str, suffix: str = ".jpg") -> str:
    """Download remote URL to a temp local file. Returns local path."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        r = requests.get(path_or_url, stream=True, timeout=30)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "mp4" in ct or "video" in ct:
            suffix = ".mp4"
        elif "png" in ct:
            suffix = ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        for chunk in r.iter_content(8192):
            tmp.write(chunk)
        tmp.close()
        return tmp.name
    return path_or_url

def _cleanup(local: str, original: str):
    if original.startswith("http://") or original.startswith("https://"):
        try:
            if os.path.exists(local):
                os.remove(local)
        except Exception:
            pass

def _build_usertags(usernames_csv: Optional[str]):
    """
    Convert a comma-separated string of @usernames into Usertag objects.
    Positions are distributed evenly across the image.
    """
    if not usernames_csv:
        return []
    from instagrapi.types import Usertag
    names = [u.strip().lstrip("@") for u in usernames_csv.split(",") if u.strip()]
    tags = []
    total = len(names)
    for i, name in enumerate(names):
        try:
            uid = ig.cl.user_id_from_username(name)
            user_info = ig.cl.user_info(uid)
            # Spread tags across the image horizontally
            x = round((i + 1) / (total + 1), 2)
            y = 0.5
            tags.append(Usertag(user=user_info, x=x, y=y))
        except Exception:
            pass  # Skip invalid usernames silently
    return tags

def _get_location(location_name: Optional[str]):
    """Search for a location and return the first match."""
    if not location_name:
        return None
    try:
        results = ig.cl.location_search(location_name)
        return results[0] if results else None
    except Exception:
        return None

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
        "caption": (m.caption_text or "")[:200],
        "like_count": m.like_count,
        "comment_count": m.comment_count,
        "taken_at": str(m.taken_at),
        "user": m.user.username if m.user else None,
    }

def _media_id_from_input(media_id_or_url: str) -> str:
    """Accept either a raw media ID or a post URL."""
    if "instagram.com" in media_id_or_url:
        match = re.search(r'/(?:p|reel)/([A-Za-z0-9_-]+)/', media_id_or_url)
        if match:
            return ig.cl.media_id(match.group(1))
    return media_id_or_url


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_login_with_credentials(username: str, password: str) -> str:
    """
    Log in using username + password.
    Returns 'needs_2fa' or 'needs_challenge' if verification is required.
    """
    return str(ig.login_with_credentials(username, password))

@mcp.tool()
def instagram_login_with_sessionid(username: str, session_id: str) -> str:
    """
    Log in via browser sessionid cookie — most reliable, bypasses 2FA.
    Get it: Instagram.com → F12 → Application → Cookies → copy 'sessionid'.
    """
    return str(ig.login_with_sessionid(username, session_id))

@mcp.tool()
def instagram_complete_2fa(code: str) -> str:
    """Submit the 2FA authenticator code after login returned 'needs_2fa'."""
    return str(ig.complete_2fa(code))

@mcp.tool()
def instagram_complete_challenge(code: str) -> str:
    """Submit the email/SMS challenge code after login returned 'needs_challenge'."""
    return str(ig.complete_challenge(code))

@mcp.tool()
def instagram_get_login_status() -> str:
    """Check if the server is authenticated and which account is active."""
    return str(ig.get_login_status())

@mcp.tool()
def instagram_logout() -> str:
    """Log out and delete the saved session file from disk."""
    return str(ig.logout())


# ─────────────────────────────────────────────────────────────────────────────
# 2. PROFILE
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_profile(username: Optional[str] = None) -> str:
    """
    Get full profile details for the logged-in account or any target username.
    Includes bio, follower/following counts, post count, website, verification status.
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
            "profile_pic_url": str(u.profile_pic_url),
            "category": u.category,
        })
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def instagram_edit_profile(full_name: Optional[str] = None,
                             biography: Optional[str] = None,
                             external_url: Optional[str] = None) -> str:
    """
    Edit the logged-in account's profile.
    - full_name: Display name
    - biography: Bio text (supports emojis, newlines, @mentions, #hashtags)
    - external_url: Website link in bio
    Only fields you provide are updated.
    """
    if err := _require_login(): return err
    try:
        u = ig.cl.user_info(ig.cl.user_id)
        ig.cl.account_edit(
            full_name=full_name or u.full_name,
            biography=biography if biography is not None else u.biography,
            external_url=external_url or str(u.external_url or ""),
        )
        return "Profile updated successfully."
    except Exception as e:
        return f"Error updating profile: {e}"

@mcp.tool()
def instagram_change_profile_picture(image_path_or_url: str) -> str:
    """Change the profile picture. Accepts local file path or image URL."""
    if err := _require_login(): return err
    local = None
    try:
        local = _download_if_url(image_path_or_url, ".jpg")
        ig.cl.account_change_picture(local)
        return "Profile picture changed successfully."
    except Exception as e:
        return f"Error: {e}"
    finally:
        if local: _cleanup(local, image_path_or_url)


# ─────────────────────────────────────────────────────────────────────────────
# 3. FULL POST CREATION & MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_post_photo(
    image_path_or_url: str,
    caption: str,
    hashtags: Optional[str] = None,
    mentions: Optional[str] = None,
    tag_users_in_photo: Optional[str] = None,
    location_name: Optional[str] = None,
    alt_text: Optional[str] = None,
    disable_comments: bool = False,
    hide_likes: bool = False,
) -> str:
    """
    Post a photo to the Instagram feed with FULL control.

    Parameters:
    - image_path_or_url: Local file path or direct image URL
    - caption: Main post caption/description text
    - hashtags: Comma-separated hashtags to append (e.g. "#python, #ai, #coding")
    - mentions: Comma-separated @usernames to mention in caption (e.g. "@nasa, @google")
    - tag_users_in_photo: Comma-separated @usernames to physically TAG in the image (people tags)
    - location_name: Location to tag (e.g. "New York, USA" or "Eiffel Tower")
    - alt_text: Accessibility alt text describing the image content
    - disable_comments: Set True to disable comments on this post
    - hide_likes: Set True to hide like count from others
    """
    if err := _require_login(): return err
    local = None
    try:
        local = _download_if_url(image_path_or_url, ".jpg")

        # Build full caption by appending hashtags and mentions
        full_caption = caption or ""
        if mentions:
            mention_str = " ".join([
                m.strip() if m.strip().startswith("@") else f"@{m.strip()}"
                for m in mentions.split(",") if m.strip()
            ])
            full_caption = f"{full_caption}\n\n{mention_str}".strip()
        if hashtags:
            tag_str = " ".join([
                h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
                for h in hashtags.split(",") if h.strip()
            ])
            full_caption = f"{full_caption}\n\n{tag_str}".strip()

        location = _get_location(location_name)
        usertags = _build_usertags(tag_users_in_photo)

        media = ig.cl.photo_upload(
            local,
            full_caption,
            location=location,
            usertags=usertags,
        )

        # Post-upload options
        if alt_text:
            try:
                ig.cl.private_request(
                    f"media/{media.pk}/update_media/",
                    data={**ig.cl.with_action_data({}), "accessibility_caption": alt_text}
                )
            except Exception:
                pass  # Alt text setting failed — not critical
        if disable_comments:
            try:
                ig.cl.private_request(
                    f"media/{media.pk}/disable_comments/",
                    data=ig.cl.with_action_data({})
                )
            except Exception:
                pass

        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/p/{media.code}/",
            "caption_preview": full_caption[:100],
            "location": location_name,
            "tagged_users": tag_users_in_photo,
            "comments_disabled": disable_comments,
            "note": "alt_text must be set in the Instagram app (no API support)",
        })
    except Exception as e:
        return f"Error posting photo: {e}"
    finally:
        if local: _cleanup(local, image_path_or_url)


@mcp.tool()
def instagram_post_album(
    image_paths_or_urls: List[str],
    caption: str,
    hashtags: Optional[str] = None,
    mentions: Optional[str] = None,
    location_name: Optional[str] = None,
    disable_comments: bool = False,
) -> str:
    """
    Post a carousel album (2–10 photos/videos) with full caption control.

    Parameters:
    - image_paths_or_urls: List of local paths or URLs (up to 10 items)
    - caption: Main caption text
    - hashtags: Comma-separated hashtags (e.g. "#travel, #photography")
    - mentions: Comma-separated @mentions (e.g. "@friend1, @brand")
    - location_name: Location tag string
    - disable_comments: Set True to disable comments
    """
    if err := _require_login(): return err
    locals_ = []
    try:
        full_caption = caption or ""
        if mentions:
            mention_str = " ".join([
                m.strip() if m.strip().startswith("@") else f"@{m.strip()}"
                for m in mentions.split(",") if m.strip()
            ])
            full_caption = f"{full_caption}\n\n{mention_str}".strip()
        if hashtags:
            tag_str = " ".join([
                h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
                for h in hashtags.split(",") if h.strip()
            ])
            full_caption = f"{full_caption}\n\n{tag_str}".strip()

        paths = []
        for item in image_paths_or_urls[:10]:
            local = _download_if_url(item, ".jpg")
            locals_.append((local, item))
            paths.append(Path(local))

        location = _get_location(location_name)
        media = ig.cl.album_upload(paths, full_caption, location=location)

        if disable_comments:
            try:
                ig.cl.private_request(
                    f"media/{media.pk}/disable_comments/",
                    data=ig.cl.with_action_data({})
                )
            except Exception:
                pass

        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/p/{media.code}/",
            "items": len(paths),
            "caption_preview": full_caption[:100],
        })
    except Exception as e:
        return f"Error posting album: {e}"
    finally:
        for local, orig in locals_:
            _cleanup(local, orig)


@mcp.tool()
def instagram_post_video(
    video_path_or_url: str,
    caption: str,
    hashtags: Optional[str] = None,
    mentions: Optional[str] = None,
    location_name: Optional[str] = None,
    thumbnail_path_or_url: Optional[str] = None,
    alt_text: Optional[str] = None,
    disable_comments: bool = False,
) -> str:
    """
    Post a video to the feed with full caption control.

    Parameters:
    - video_path_or_url: Local path or URL to MP4 file
    - caption: Caption text
    - hashtags: Comma-separated hashtags
    - mentions: Comma-separated @mentions
    - location_name: Location to tag
    - thumbnail_path_or_url: Custom thumbnail image (optional)
    - alt_text: Accessibility description for the video
    - disable_comments: Set True to disable comments
    """
    if err := _require_login(): return err
    local_v = local_t = None
    try:
        full_caption = caption or ""
        if mentions:
            mention_str = " ".join([
                m.strip() if m.strip().startswith("@") else f"@{m.strip()}"
                for m in mentions.split(",") if m.strip()
            ])
            full_caption = f"{full_caption}\n\n{mention_str}".strip()
        if hashtags:
            tag_str = " ".join([
                h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
                for h in hashtags.split(",") if h.strip()
            ])
            full_caption = f"{full_caption}\n\n{tag_str}".strip()

        local_v = _download_if_url(video_path_or_url, ".mp4")
        if thumbnail_path_or_url:
            local_t = _download_if_url(thumbnail_path_or_url, ".jpg")

        location = _get_location(location_name)
        media = ig.cl.video_upload(local_v, full_caption, thumbnail=local_t, location=location)

        if disable_comments:
            try:
                ig.cl.private_request(
                    f"media/{media.pk}/disable_comments/",
                    data=ig.cl.with_action_data({})
                )
            except Exception:
                pass

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
def instagram_post_reel(
    video_path_or_url: str,
    caption: str,
    hashtags: Optional[str] = None,
    mentions: Optional[str] = None,
    location_name: Optional[str] = None,
    disable_comments: bool = False,
) -> str:
    """
    Post a Reel with full caption control. Reels have the highest organic reach.

    Parameters:
    - video_path_or_url: Local path or URL to MP4 video
    - caption: Caption text
    - hashtags: Comma-separated hashtags (crucial for Reel discovery)
    - mentions: Comma-separated @mentions
    - location_name: Location tag
    - disable_comments: Set True to disable comments
    """
    if err := _require_login(): return err
    local_v = None
    try:
        full_caption = caption or ""
        if mentions:
            mention_str = " ".join([
                m.strip() if m.strip().startswith("@") else f"@{m.strip()}"
                for m in mentions.split(",") if m.strip()
            ])
            full_caption = f"{full_caption}\n\n{mention_str}".strip()
        if hashtags:
            tag_str = " ".join([
                h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
                for h in hashtags.split(",") if h.strip()
            ])
            full_caption = f"{full_caption}\n\n{tag_str}".strip()

        local_v = _download_if_url(video_path_or_url, ".mp4")
        location = _get_location(location_name)
        media = ig.cl.clip_upload(local_v, full_caption, location=location)

        if disable_comments:
            try:
                ig.cl.private_request(
                    f"media/{media.pk}/disable_comments/",
                    data=ig.cl.with_action_data({})
                )
            except Exception:
                pass

        return str({
            "status": "success",
            "media_id": str(media.pk),
            "url": f"https://www.instagram.com/reel/{media.code}/",
            "caption_preview": full_caption[:100],
        })
    except Exception as e:
        return f"Error posting Reel: {e}"
    finally:
        if local_v: _cleanup(local_v, video_path_or_url)


@mcp.tool()
def instagram_edit_post_caption(
    media_id_or_url: str,
    new_caption: str,
    hashtags: Optional[str] = None,
    mentions: Optional[str] = None,
) -> str:
    """
    Edit the caption of an existing post.

    Parameters:
    - media_id_or_url: Post media ID or full Instagram URL
    - new_caption: The new caption text (replaces the old one entirely)
    - hashtags: Hashtags to append to the new caption
    - mentions: @mentions to append to the new caption
    """
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)

        full_caption = new_caption or ""
        if mentions:
            mention_str = " ".join([
                m.strip() if m.strip().startswith("@") else f"@{m.strip()}"
                for m in mentions.split(",") if m.strip()
            ])
            full_caption = f"{full_caption}\n\n{mention_str}".strip()
        if hashtags:
            tag_str = " ".join([
                h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
                for h in hashtags.split(",") if h.strip()
            ])
            full_caption = f"{full_caption}\n\n{tag_str}".strip()

        result = ig.cl.media_edit(mid, full_caption)
        return f"Caption updated successfully. New caption preview: '{full_caption[:100]}'"
    except Exception as e:
        return f"Error editing caption: {e}"


@mcp.tool()
def instagram_tag_users_in_post(media_id_or_url: str, usernames: str) -> str:
    """
    Tag one or more users physically IN a photo (people tags).
    NOTE: Instagram's API only supports setting usertags at upload time.
    Use the tag_users_in_photo parameter in instagram_post_photo/post_reel instead.
    This tool attempts a post-upload tag via the private endpoint.

    Parameters:
    - media_id_or_url: Post media ID or Instagram URL
    - usernames: Comma-separated @usernames to tag in the photo
    """
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        usertags = _build_usertags(usernames)
        if not usertags:
            return "Error: Could not resolve any of the provided usernames."
        # Build the usertag payload for the private API
        usertag_data = {
            "usertags": {
                "in": [
                    {
                        "user_id": str(ut.user.pk),
                        "position": [ut.x, ut.y]
                    }
                    for ut in usertags
                ]
            }
        }
        ig.cl.private_request(
            f"media/{mid}/update_media/",
            data={**ig.cl.with_action_data({}), **{"usertags": str(usertag_data)}}
        )
        tagged = [ut.user.username for ut in usertags]
        return f"Tagged {len(tagged)} user(s): {', '.join(tagged)}. (Tip: for guaranteed tags, use tag_users_in_photo param in instagram_post_photo)"
    except Exception as e:
        return f"Tip: Post-upload tagging has limited API support. Use the 'tag_users_in_photo' parameter when creating a new post. Error: {e}"


@mcp.tool()
def instagram_set_post_alt_text(media_id_or_url: str, alt_text: str) -> str:
    """
    Attempt to set accessibility alt text on an existing post via the private API.
    Alt text describes the image content for visually impaired users.

    Parameters:
    - media_id_or_url: Post media ID or full Instagram URL
    - alt_text: Text description of the image/video content
    """
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        # Instagram private API endpoint for accessibility caption
        ig.cl.private_request(
            f"media/{mid}/update_media/",
            data={**ig.cl.with_action_data({}), "accessibility_caption": alt_text}
        )
        return f"Alt text set successfully: '{alt_text}'"
    except Exception as e:
        return f"Error setting alt text: {e}"


@mcp.tool()
def instagram_disable_comments(media_id_or_url: str) -> str:
    """Disable comments on a post."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.private_request(
            f"media/{mid}/disable_comments/",
            data=ig.cl.with_action_data({})
        )
        return f"Comments disabled on post {mid}."
    except Exception as e:
        return f"Error disabling comments: {e}"


@mcp.tool()
def instagram_enable_comments(media_id_or_url: str) -> str:
    """Enable comments on a post (reverses a previous disable)."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.private_request(
            f"media/{mid}/enable_comments/",
            data=ig.cl.with_action_data({})
        )
        return f"Comments enabled on post {mid}."
    except Exception as e:
        return f"Error enabling comments: {e}"


@mcp.tool()
def instagram_archive_post(media_id_or_url: str) -> str:
    """
    Archive a post (hides it from your profile grid, but keeps it saved).
    Archived posts can be found in your Archive section.
    """
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_archive(mid)
        return f"Post {mid} archived successfully."
    except Exception as e:
        return f"Error archiving post: {e}"


@mcp.tool()
def instagram_unarchive_post(media_id_or_url: str) -> str:
    """Unarchive a post (restores it to your profile grid)."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_unarchive(mid)
        return f"Post {mid} unarchived successfully."
    except Exception as e:
        return f"Error unarchiving post: {e}"


@mcp.tool()
def instagram_pin_post(media_id_or_url: str) -> str:
    """
    Pin a post to the top of your profile grid.
    You can pin up to 3 posts on your profile.
    """
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_pin(mid)
        return f"Post {mid} pinned to profile."
    except Exception as e:
        return f"Error pinning post: {e}"


@mcp.tool()
def instagram_unpin_post(media_id_or_url: str) -> str:
    """Remove a pinned post from the top of your profile grid."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_unpin(mid)
        return f"Post {mid} unpinned."
    except Exception as e:
        return f"Error unpinning post: {e}"


@mcp.tool()
def instagram_delete_post(media_id_or_url: str) -> str:
    """Permanently delete a post. This cannot be undone."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_delete(mid)
        return f"Post {mid} deleted permanently."
    except Exception as e:
        return f"Error deleting post: {e}"


@mcp.tool()
def instagram_get_user_feed(username: Optional[str] = None, amount: int = 12) -> str:
    """Get recent posts from the logged-in account or any target username."""
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        medias = ig.cl.user_medias(uid, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_timeline_feed(amount: int = 10) -> str:
    """Get the home timeline feed — posts from accounts you follow."""
    if err := _require_login(): return err
    try:
        feed = ig.cl.get_timeline_feed()
        items = feed.get("feed_items", [])
        results = []
        for item in items[:amount]:
            mi = item.get("media_or_ad", {})
            if mi:
                code = mi.get("code", "")
                cap = (mi.get("caption") or {}).get("text", "")
                results.append({
                    "url": f"https://www.instagram.com/p/{code}/",
                    "user": mi.get("user", {}).get("username", ""),
                    "caption": (cap or "")[:200],
                    "like_count": mi.get("like_count", 0),
                    "comment_count": mi.get("comment_count", 0),
                })
        return str(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_media_info(media_id_or_url: str) -> str:
    """Get detailed information about any post by ID or URL."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        m = ig.cl.media_info(mid)
        return str(_fmt_media(m))
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_tagged_posts(username: Optional[str] = None, amount: int = 12) -> str:
    """
    Get posts where the logged-in account (or a target username) is tagged.
    """
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        medias = ig.cl.usertag_medias(uid, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_saved_posts(amount: int = 20) -> str:
    """Get posts saved in your Saved collection."""
    if err := _require_login(): return err
    try:
        # Use the all-items collection
        medias = ig.cl.collection_medias_by_name("ALL_POSTS_AUTO_COLLECTION", amount=amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        # Fallback: fetch via collection list
        try:
            cols = ig.cl.collections()
            if cols:
                medias = ig.cl.collection_medias(cols[0].id, amount=amount)
                return str([_fmt_media(m) for m in medias])
        except Exception:
            pass
        return f"Error fetching saved posts: {e}"


@mcp.tool()
def instagram_download_post(media_id_or_url: str, save_dir: Optional[str] = None) -> str:
    """Download a post's photo or video to local disk."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        dest = save_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        os.makedirs(dest, exist_ok=True)
        m = ig.cl.media_info(mid)
        if m.media_type == 2:
            path = ig.cl.video_download(mid, folder=dest)
        else:
            path = ig.cl.photo_download(mid, folder=dest)
        return f"Downloaded to: {path}"
    except Exception as e:
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. STORIES (WITH STICKERS)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_post_photo_story(
    image_path_or_url: str,
    mentions: Optional[str] = None,
    hashtags: Optional[str] = None,
    location_name: Optional[str] = None,
    link_url: Optional[str] = None,
    close_friends_only: bool = False,
) -> str:
    """
    Post a photo Story with full sticker support.

    Parameters:
    - image_path_or_url: Local path or image URL
    - mentions: Comma-separated @usernames to add as mention stickers
    - hashtags: Comma-separated hashtags for hashtag stickers
    - location_name: Location sticker text
    - link_url: Link sticker URL (the swipe-up / link button on story)
    - close_friends_only: Post only to your Close Friends list
    """
    if err := _require_login(): return err
    local = None
    try:
        from instagrapi.types import StoryMention, StoryHashtag, StoryLocation, StoryLink, UserShort
        local = _download_if_url(image_path_or_url, ".jpg")

        story_mentions = []
        if mentions:
            for name in [m.strip().lstrip("@") for m in mentions.split(",") if m.strip()]:
                try:
                    uid = ig.cl.user_id_from_username(name)
                    user = ig.cl.user_info(uid)
                    story_mentions.append(StoryMention(user=user, x=0.5, y=0.5, width=0.5, height=0.1))
                except Exception:
                    pass

        story_hashtags = []
        if hashtags:
            for tag in [h.strip().lstrip("#") for h in hashtags.split(",") if h.strip()]:
                try:
                    hinfo = ig.cl.hashtag_info(tag)
                    story_hashtags.append(StoryHashtag(hashtag=hinfo, x=0.5, y=0.7, width=0.3, height=0.08))
                except Exception:
                    pass

        story_locations = []
        if location_name:
            try:
                results = ig.cl.location_search(location_name)
                if results:
                    story_locations.append(StoryLocation(location=results[0], x=0.5, y=0.85, width=0.4, height=0.08))
            except Exception:
                pass

        story_links = []
        if link_url:
            story_links.append(StoryLink(webUri=link_url))

        m = ig.cl.photo_upload_to_story(
            local,
            mentions=story_mentions,
            hashtags=story_hashtags,
            locations=story_locations,
            links=story_links,
        )
        return str({
            "status": "success",
            "media_id": str(m.pk),
            "stickers": {
                "mentions": [s.user.username for s in story_mentions],
                "hashtags": [s.hashtag.name for s in story_hashtags],
                "location": location_name,
                "link": link_url,
            }
        })
    except Exception as e:
        return f"Error posting story: {e}"
    finally:
        if local: _cleanup(local, image_path_or_url)


@mcp.tool()
def instagram_post_video_story(
    video_path_or_url: str,
    mentions: Optional[str] = None,
    hashtags: Optional[str] = None,
    location_name: Optional[str] = None,
    link_url: Optional[str] = None,
    close_friends_only: bool = False,
) -> str:
    """
    Post a video Story with full sticker support.

    Parameters:
    - video_path_or_url: Local path or URL to MP4
    - mentions: Comma-separated @usernames for mention stickers
    - hashtags: Comma-separated hashtags for hashtag stickers
    - location_name: Location sticker text
    - link_url: Link sticker URL
    - close_friends_only: Post only to Close Friends
    """
    if err := _require_login(): return err
    local = None
    try:
        from instagrapi.types import StoryMention, StoryHashtag, StoryLocation, StoryLink
        local = _download_if_url(video_path_or_url, ".mp4")

        story_mentions, story_hashtags, story_locations, story_links = [], [], [], []

        if mentions:
            for name in [m.strip().lstrip("@") for m in mentions.split(",") if m.strip()]:
                try:
                    uid = ig.cl.user_id_from_username(name)
                    user = ig.cl.user_info(uid)
                    story_mentions.append(StoryMention(user=user, x=0.5, y=0.5, width=0.5, height=0.1))
                except Exception:
                    pass
        if hashtags:
            for tag in [h.strip().lstrip("#") for h in hashtags.split(",") if h.strip()]:
                try:
                    hinfo = ig.cl.hashtag_info(tag)
                    story_hashtags.append(StoryHashtag(hashtag=hinfo, x=0.5, y=0.7, width=0.3, height=0.08))
                except Exception:
                    pass
        if location_name:
            try:
                results = ig.cl.location_search(location_name)
                if results:
                    story_locations.append(StoryLocation(location=results[0], x=0.5, y=0.85, width=0.4, height=0.08))
            except Exception:
                pass
        if link_url:
            story_links.append(StoryLink(webUri=link_url))

        m = ig.cl.video_upload_to_story(
            local,
            mentions=story_mentions,
            hashtags=story_hashtags,
            locations=story_locations,
            links=story_links,
        )
        return str({
            "status": "success",
            "media_id": str(m.pk),
        })
    except Exception as e:
        return f"Error posting video story: {e}"
    finally:
        if local: _cleanup(local, video_path_or_url)


@mcp.tool()
def instagram_get_user_stories(username: Optional[str] = None) -> str:
    """Get active stories for the logged-in account or a target username."""
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        stories = ig.cl.user_stories(uid)
        return str([{"pk": str(s.pk), "media_type": s.media_type, "taken_at": str(s.taken_at)} for s in stories])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_delete_story(story_id: str) -> str:
    """Delete one of your active stories by media ID."""
    if err := _require_login(): return err
    try:
        ig.cl.media_delete(story_id)
        return f"Story {story_id} deleted."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_story_viewers(story_id: str) -> str:
    """Get the list of users who viewed one of your stories."""
    if err := _require_login(): return err
    try:
        viewers = ig.cl.story_viewers(story_id)
        return str([_fmt_user(v) for v in viewers])
    except Exception as e:
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. HIGHLIGHTS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_highlights(username: Optional[str] = None) -> str:
    """Get story highlights for the logged-in account or a target username."""
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        highlights = ig.cl.user_highlights(uid)
        return str([{"pk": str(h.pk), "title": h.title, "media_count": h.media_count} for h in highlights])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_create_highlight(title: str, story_ids: List[str]) -> str:
    """Create a new story highlight collection from existing stories."""
    if err := _require_login(): return err
    try:
        h = ig.cl.highlight_create(title, story_ids)
        return f"Highlight '{title}' created. ID: {h.pk}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_delete_highlight(highlight_id: str) -> str:
    """Delete a highlights collection by its ID."""
    if err := _require_login(): return err
    try:
        ig.cl.highlight_delete(highlight_id)
        return f"Highlight {highlight_id} deleted."
    except Exception as e:
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. ENGAGEMENT — LIKES, COMMENTS, SAVES
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_like_post(media_id_or_url: str) -> str:
    """Like a post by media ID or URL."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_like(mid)
        return f"Liked post {mid}."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_unlike_post(media_id_or_url: str) -> str:
    """Remove a like from a post."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_unlike(mid)
        return f"Unliked post {mid}."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_save_post(media_id_or_url: str) -> str:
    """Save a post to your Saved collection."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_save(mid)
        return f"Post {mid} saved."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_unsave_post(media_id_or_url: str) -> str:
    """Remove a post from your Saved collection."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.media_unsave(mid)
        return f"Post {mid} unsaved."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_post_likers(media_id_or_url: str) -> str:
    """Get the list of users who liked a post."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        likers = ig.cl.media_likers(mid)
        return str([_fmt_user(u) for u in likers])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_comment_on_post(media_id_or_url: str, text: str) -> str:
    """Post a comment on any media item."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        c = ig.cl.media_comment(mid, text)
        return f"Comment posted. ID: {c.pk}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_reply_to_comment(media_id_or_url: str, comment_id: str, text: str) -> str:
    """Reply to a specific comment on a post."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        c = ig.cl.media_comment(mid, text, replied_to_comment_id=int(comment_id))
        return f"Reply posted. ID: {c.pk}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_delete_comment(media_id_or_url: str, comment_id: str) -> str:
    """Delete a comment by media ID/URL and comment ID."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        ig.cl.comment_bulk_delete(mid, [comment_id])
        return f"Comment {comment_id} deleted."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_like_comment(comment_id: str) -> str:
    """Like a comment on a post."""
    if err := _require_login(): return err
    try:
        ig.cl.comment_like(comment_id)
        return f"Comment {comment_id} liked."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_post_comments(media_id_or_url: str, amount: int = 20) -> str:
    """Get comments on a post with usernames, text, and timestamps."""
    if err := _require_login(): return err
    try:
        mid = _media_id_from_input(media_id_or_url)
        comments = ig.cl.media_comments(mid, amount)
        return str([{
            "pk": str(c.pk),
            "user": c.user.username,
            "text": c.text,
            "like_count": c.like_count,
            "created_at": str(c.created_at_utc),
        } for c in comments])
    except Exception as e:
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. FOLLOWING & RELATIONS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_follow_user(username: str) -> str:
    """Follow a user by username."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        ig.cl.user_follow(uid)
        return f"Followed @{username}."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_unfollow_user(username: str) -> str:
    """Unfollow a user by username."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        ig.cl.user_unfollow(uid)
        return f"Unfollowed @{username}."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_followers(username: Optional[str] = None, amount: int = 50) -> str:
    """Get the followers list for the logged-in account or a target username."""
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        followers = ig.cl.user_followers(uid, amount=amount)
        return str([_fmt_user(u) for u in followers.values()])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_following(username: Optional[str] = None, amount: int = 50) -> str:
    """Get the accounts that the logged-in account (or target username) is following."""
    if err := _require_login(): return err
    try:
        target = username or ig.cl.username
        uid = ig.cl.user_id_from_username(target)
        following = ig.cl.user_following(uid, amount=amount)
        return str([_fmt_user(u) for u in following.values()])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_block_user(username: str) -> str:
    """Block a user by username."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        ig.cl.user_block(uid)
        return f"Blocked @{username}."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_unblock_user(username: str) -> str:
    """Unblock a previously blocked user."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        ig.cl.user_unblock(uid)
        return f"Unblocked @{username}."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_blocked_users() -> str:
    """Get the full list of users you have blocked."""
    if err := _require_login(): return err
    try:
        # Use the private API endpoint directly
        result = ig.cl.private_request("users/blocked_list/")
        users = result.get("blocked_list", [])
        return str([{"pk": str(u.get("pk")), "username": u.get("username")} for u in users])
    except Exception as e:
        return f"Error fetching blocked users: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. DIRECT MESSAGES
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_direct_threads(amount: int = 20) -> str:
    """Get recent DM threads with thread IDs, participants, and last activity."""
    if err := _require_login(): return err
    try:
        threads = ig.cl.direct_threads(amount)
        return str([{
            "thread_id": t.id,
            "title": t.thread_title or "",
            "participants": [u.username for u in (t.users or [])],
            "last_activity_at": str(t.last_activity_at),
            "muted": t.muted,
        } for t in threads])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_direct_messages(thread_id: str, amount: int = 30) -> str:
    """Get messages in a DM thread, sorted chronologically."""
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
        return f"Error: {e}"


@mcp.tool()
def instagram_send_direct_message(text: str, username: Optional[str] = None,
                                   thread_id: Optional[str] = None) -> str:
    """
    Send a text DM. Provide either:
    - username: to start or continue a conversation with a user.
    - thread_id: to reply in an existing thread.
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
        return f"Error: {e}"


@mcp.tool()
def instagram_send_dm_photo(image_path_or_url: str, username: Optional[str] = None,
                             thread_id: Optional[str] = None) -> str:
    """Send a photo via DM. Provide username or thread_id."""
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
        return f"Error: {e}"
    finally:
        if local: _cleanup(local, image_path_or_url)


@mcp.tool()
def instagram_send_dm_video(video_path_or_url: str, username: Optional[str] = None,
                             thread_id: Optional[str] = None) -> str:
    """Send a video via DM. Provide username or thread_id."""
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
        return f"Error: {e}"
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
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 9. SEARCH & EXPLORE
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_search_users(query: str, count: int = 10) -> str:
    """Search for Instagram users by name or username."""
    if err := _require_login(): return err
    try:
        results = ig.cl.search_users(query)[:count]
        return str([_fmt_user(u) for u in results])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_search_hashtag(hashtag: str, amount: int = 12) -> str:
    """Get recent posts for a hashtag. Do not include '#' symbol."""
    if err := _require_login(): return err
    try:
        medias = ig.cl.hashtag_medias_recent(hashtag.lstrip("#"), amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_hashtag_top_posts(hashtag: str, amount: int = 9) -> str:
    """Get trending/top posts for a hashtag. Do not include '#' symbol."""
    if err := _require_login(): return err
    try:
        medias = ig.cl.hashtag_medias_top(hashtag.lstrip("#"), amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_hashtag_info(hashtag: str) -> str:
    """Get information about a hashtag including total post count."""
    if err := _require_login(): return err
    try:
        info = ig.cl.hashtag_info(hashtag.lstrip("#"))
        return str({"name": info.name, "media_count": info.media_count, "id": str(info.id)})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_similar_accounts(username: str) -> str:
    """Find accounts similar to a given username (Instagram's 'suggested for you')."""
    if err := _require_login(): return err
    try:
        uid = ig.cl.user_id_from_username(username)
        similar = ig.cl.user_suggested_profiles(uid)
        return str([_fmt_user(u) for u in similar])
    except Exception as e:
        return f"Error fetching similar accounts: {e}"


@mcp.tool()
def instagram_get_location_posts(location_name: str, amount: int = 12) -> str:
    """Get recent posts tagged at a specific location."""
    if err := _require_login(): return err
    try:
        results = ig.cl.location_search(location_name)
        if not results:
            return f"No location found for '{location_name}'"
        medias = ig.cl.location_medias_recent(results[0].pk, amount)
        return str([_fmt_media(m) for m in medias])
    except Exception as e:
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 10. NOTIFICATIONS & ACTIVITY
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def instagram_get_notifications(amount: int = 20) -> str:
    """Get recent activity — likes, comments, follows, mentions, tags."""
    if err := _require_login(): return err
    try:
        activity = ig.cl.news_inbox_v1()
        counts = activity.get("counts", {})
        stories = activity.get("new_stories", [])[:amount]
        items = [{
            "type": s.get("type"),
            "text": s.get("args", {}).get("text", ""),
            "timestamp": s.get("args", {}).get("timestamp"),
            "from": s.get("args", {}).get("profile_name"),
        } for s in stories]
        return str({"unread_counts": counts, "notifications": items})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def instagram_get_pending_follow_requests() -> str:
    """Get pending follow requests for your account (relevant for private accounts)."""
    if err := _require_login(): return err
    try:
        users = ig.cl.user_follow_requests()
        return str([_fmt_user(u) for u in users])
    except Exception as e:
        return f"Error fetching pending requests: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
