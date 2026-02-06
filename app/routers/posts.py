"""Posts API router."""

from pathlib import Path
from typing import Optional

import frontmatter
import markdown
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.config import Settings, get_settings
from app.schemas.post import Post, PostList, PostMetadata, TagList
from app.security import limiter, verify_api_key

router = APIRouter(prefix="/api/posts", tags=["posts"])


def calculate_reading_time(content: str) -> int:
    """Calculate reading time in minutes (assuming 200 words per minute)."""
    words = len(content.split())
    minutes = max(1, round(words / 200))
    return minutes


def load_post_from_path(post_path: Path, slug: str) -> PostMetadata | None:
    """Load post metadata from a path (either folder/README.md or .md file)."""
    try:
        post = frontmatter.load(post_path)
        reading_time = calculate_reading_time(post.content)
        metadata = PostMetadata(
            title=post.get("title", slug),
            slug=post.get("slug", slug),
            description=post.get("description"),
            author=post.get("author"),
            date=post.get("date"),
            tags=post.get("tags", []),
            published=post.get("published", True),
            reading_time_minutes=reading_time,
        )
        if metadata.published:
            return metadata
    except Exception:
        pass
    return None


def get_all_posts(settings: Settings) -> list[PostMetadata]:
    """Get all published posts from the content directory."""
    posts_dir = Path(settings.content_repo_path) / "posts"
    posts: list[PostMetadata] = []

    if not posts_dir.exists():
        return posts

    # Support both folder-based (posts/slug/README.md) and flat (posts/slug.md) structures
    # Check folders first (new structure)
    for folder in posts_dir.iterdir():
        if folder.is_dir():
            readme_path = folder / "README.md"
            if readme_path.exists():
                metadata = load_post_from_path(readme_path, folder.name)
                if metadata:
                    posts.append(metadata)

    # Also check flat .md files (legacy structure)
    for md_file in posts_dir.glob("*.md"):
        if md_file.is_file():
            metadata = load_post_from_path(md_file, md_file.stem)
            if metadata:
                # Avoid duplicates if both structures exist
                if not any(p.slug == metadata.slug for p in posts):
                    posts.append(metadata)

    posts.sort(key=lambda p: p.date or "", reverse=True)
    return posts


def find_post_file(posts_dir: Path, slug: str) -> Path | None:
    """Find the post file for a given slug (supports both folder and flat structures)."""
    # Check folder structure first (posts/slug/README.md)
    folder_path = posts_dir / slug / "README.md"
    if folder_path.exists():
        return folder_path

    # Fall back to flat structure (posts/slug.md)
    flat_path = posts_dir / f"{slug}.md"
    if flat_path.exists():
        return flat_path

    return None


def matches_search(post: PostMetadata, query: str) -> bool:
    """Check if a post matches the search query."""
    query_lower = query.lower()
    terms = query_lower.split()

    searchable = f"{post.title} {post.description or ''} {' '.join(post.tags)}".lower()

    # All terms must match (AND logic)
    return all(term in searchable for term in terms)


@router.get("", response_model=PostList)
@limiter.limit("60/minute")
async def list_posts(
    request: Request,
    q: Optional[str] = Query(None, description="Search query (title, tags, description)"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    _api_key: str = Depends(verify_api_key),
    settings: Settings = Depends(get_settings),
) -> PostList:
    """List all published posts with optional search and tag filter.

    Args:
        request: The FastAPI request object (for rate limiting).
        q: Optional search query (searches title, tags, description).
        tag: Optional tag filter.
        _api_key: Validated API key (dependency).
        settings: Application settings.

    Returns:
        List of post metadata.
    """
    posts = get_all_posts(settings)

    # Apply tag filter
    if tag:
        posts = [p for p in posts if tag.lower() in [t.lower() for t in p.tags]]

    # Apply search filter
    if q:
        posts = [p for p in posts if matches_search(p, q)]

    return PostList(posts=posts, total=len(posts))


@router.get("/tags", response_model=TagList)
@limiter.limit("60/minute")
async def list_tags(
    request: Request,
    _api_key: str = Depends(verify_api_key),
    settings: Settings = Depends(get_settings),
) -> TagList:
    """List all unique tags from published posts.

    Args:
        request: The FastAPI request object (for rate limiting).
        _api_key: Validated API key (dependency).
        settings: Application settings.

    Returns:
        List of unique tags sorted alphabetically.
    """
    posts = get_all_posts(settings)
    all_tags: set[str] = set()

    for post in posts:
        all_tags.update(post.tags)

    sorted_tags = sorted(all_tags, key=str.lower)
    return TagList(tags=sorted_tags, total=len(sorted_tags))


@router.get("/{slug}", response_model=Post)
@limiter.limit("60/minute")
async def get_post(
    slug: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
    settings: Settings = Depends(get_settings),
) -> Post:
    """Get a single post by slug.

    Args:
        slug: The post slug.
        request: The FastAPI request object (for rate limiting).
        _api_key: Validated API key (dependency).
        settings: Application settings.

    Returns:
        The full post with content.

    Raises:
        HTTPException: If post not found.
    """
    posts_dir = Path(settings.content_repo_path) / "posts"
    post_file = find_post_file(posts_dir, slug)

    if not post_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post '{slug}' not found",
        )

    try:
        post = frontmatter.load(post_file)
        html_content = markdown.markdown(
            post.content,
            extensions=["fenced_code", "codehilite", "tables", "toc"],
        )
        reading_time = calculate_reading_time(post.content)

        return Post(
            title=post.get("title", slug),
            slug=post.get("slug", slug),
            description=post.get("description"),
            author=post.get("author"),
            date=post.get("date"),
            tags=post.get("tags", []),
            published=post.get("published", True),
            reading_time_minutes=reading_time,
            content=post.content,
            html_content=html_content,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading post: {e}",
        ) from e


@router.get("/{slug}/related", response_model=PostList)
@limiter.limit("60/minute")
async def get_related_posts(
    slug: str,
    request: Request,
    limit: int = Query(3, ge=1, le=10, description="Number of related posts to return"),
    _api_key: str = Depends(verify_api_key),
    settings: Settings = Depends(get_settings),
) -> PostList:
    """Get related posts based on shared tags.

    Args:
        slug: The post slug to find related posts for.
        request: The FastAPI request object (for rate limiting).
        limit: Maximum number of related posts to return.
        _api_key: Validated API key (dependency).
        settings: Application settings.

    Returns:
        List of related posts sorted by tag overlap, then by date.
    """
    posts_dir = Path(settings.content_repo_path) / "posts"
    post_file = find_post_file(posts_dir, slug)

    if not post_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post '{slug}' not found",
        )

    # Load the current post to get its tags
    try:
        current_post = frontmatter.load(post_file)
        current_tags = set(t.lower() for t in current_post.get("tags", []))
    except Exception:
        current_tags = set()

    # Get all posts except the current one
    all_posts = get_all_posts(settings)
    other_posts = [p for p in all_posts if p.slug != slug]

    if not current_tags:
        # No tags - just return recent posts
        return PostList(posts=other_posts[:limit], total=min(limit, len(other_posts)))

    # Score posts by number of shared tags
    def tag_overlap_score(post: PostMetadata) -> int:
        post_tags = set(t.lower() for t in post.tags)
        return len(current_tags & post_tags)

    # Sort by tag overlap (desc), then by date (desc)
    scored_posts = [(p, tag_overlap_score(p)) for p in other_posts]
    scored_posts.sort(key=lambda x: (x[1], x[0].date or ""), reverse=True)

    # Filter to only posts with at least one shared tag, or fall back to recent
    related = [p for p, score in scored_posts if score > 0][:limit]

    if len(related) < limit:
        # Fill with recent posts if not enough related
        remaining = limit - len(related)
        recent = [p for p, _ in scored_posts if p not in related][:remaining]
        related.extend(recent)

    return PostList(posts=related, total=len(related))
