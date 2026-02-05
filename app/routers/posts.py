"""Posts API router."""

from pathlib import Path

import frontmatter
import markdown
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.schemas.post import Post, PostList, PostMetadata
from app.security import limiter, verify_api_key

router = APIRouter(prefix="/api/posts", tags=["posts"])


def get_posts_dir(settings: Settings = Depends(get_settings)) -> Path:
    """Get the posts directory path."""
    return Path(settings.content_repo_path) / "posts"


@router.get("", response_model=PostList)
@limiter.limit("60/minute")
async def list_posts(
    request: Request,
    _api_key: str = Depends(verify_api_key),
    settings: Settings = Depends(get_settings),
) -> PostList:
    """List all published posts.

    Args:
        request: The FastAPI request object (for rate limiting).
        _api_key: Validated API key (dependency).
        settings: Application settings.

    Returns:
        List of post metadata.
    """
    posts_dir = Path(settings.content_repo_path) / "posts"
    posts: list[PostMetadata] = []

    if not posts_dir.exists():
        return PostList(posts=[], total=0)

    for md_file in posts_dir.glob("*.md"):
        try:
            post = frontmatter.load(md_file)
            metadata = PostMetadata(
                title=post.get("title", md_file.stem),
                slug=post.get("slug", md_file.stem),
                description=post.get("description"),
                author=post.get("author"),
                date=post.get("date"),
                tags=post.get("tags", []),
                published=post.get("published", True),
            )
            if metadata.published:
                posts.append(metadata)
        except Exception:
            continue

    posts.sort(key=lambda p: p.date or "", reverse=True)
    return PostList(posts=posts, total=len(posts))


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
    md_file = posts_dir / f"{slug}.md"

    if not md_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post '{slug}' not found",
        )

    try:
        post = frontmatter.load(md_file)
        html_content = markdown.markdown(
            post.content,
            extensions=["fenced_code", "codehilite", "tables", "toc"],
        )

        return Post(
            title=post.get("title", slug),
            slug=post.get("slug", slug),
            description=post.get("description"),
            author=post.get("author"),
            date=post.get("date"),
            tags=post.get("tags", []),
            published=post.get("published", True),
            content=post.content,
            html_content=html_content,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading post: {e}",
        ) from e
