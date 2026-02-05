"""Post-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class PostMetadata(BaseModel):
    """Metadata for a post (from frontmatter)."""

    title: str
    slug: str
    description: str | None = None
    author: str | None = None
    date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    published: bool = True


class Post(PostMetadata):
    """Full post with content."""

    content: str
    html_content: str


class PostList(BaseModel):
    """Response model for list of posts."""

    posts: list[PostMetadata]
    total: int
