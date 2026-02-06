"""Tests for posts API router."""

import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.main import app
from app.routers.posts import (
    calculate_reading_time,
    find_post_file,
    get_all_posts,
    load_post_from_path,
    matches_search,
)
from app.schemas.post import PostMetadata

# Test API key for testing
TEST_API_KEY = "test-api-key-12345"


def get_test_settings_with_content_path(content_path: str) -> Settings:
    """Create test settings with custom content path."""
    return Settings(
        content_repo_path=content_path,
        api_key=TEST_API_KEY,
    )


@pytest.fixture
def temp_content_dir():
    """Create a temporary directory with test post content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        posts_dir = Path(tmpdir) / "posts"
        posts_dir.mkdir()

        # Create folder-based post 1
        post1_dir = posts_dir / "test-post-1"
        post1_dir.mkdir()
        (post1_dir / "README.md").write_text("""---
title: "Test Post 1"
slug: "test-post-1"
description: "This is the first test post about Python programming."
author: "Test Author"
date: 2024-01-15
tags: ["python", "testing", "api"]
published: true
---

This is the content of test post 1.
It has multiple lines and talks about Python and testing.
Let's add more words to test reading time calculation.
Word word word word word word word word word word.
Word word word word word word word word word word.
Word word word word word word word word word word.
""")

        # Create folder-based post 2
        post2_dir = posts_dir / "test-post-2"
        post2_dir.mkdir()
        (post2_dir / "README.md").write_text("""---
title: "Test Post 2"
slug: "test-post-2"
description: "Second test post about JavaScript and web development."
author: "Test Author"
date: 2024-02-20
tags: ["javascript", "web", "api"]
published: true
---

This is the content of test post 2.
It discusses JavaScript and frontend development.
More content here for testing purposes.
""")

        # Create folder-based post 3 (unpublished)
        post3_dir = posts_dir / "unpublished-post"
        post3_dir.mkdir()
        (post3_dir / "README.md").write_text("""---
title: "Unpublished Post"
slug: "unpublished-post"
description: "This post should not appear in listings."
author: "Test Author"
date: 2024-03-01
tags: ["draft"]
published: false
---

This is an unpublished post.
""")

        # Create flat-structure post (legacy .md file)
        (posts_dir / "legacy-post.md").write_text("""---
title: "Legacy Post"
slug: "legacy-post"
description: "A legacy flat-structure post."
author: "Test Author"
date: 2024-01-01
tags: ["legacy", "python"]
published: true
---

This is a legacy post in flat structure.
""")

        # Create folder-based post 4 for related posts testing
        post4_dir = posts_dir / "related-post"
        post4_dir.mkdir()
        (post4_dir / "README.md").write_text("""---
title: "Related Post"
slug: "related-post"
description: "A post related to test post 1 by tags."
author: "Test Author"
date: 2024-01-10
tags: ["python", "testing"]
published: true
---

This post shares tags with test post 1.
""")

        yield tmpdir


@pytest.fixture
def test_settings(temp_content_dir):
    """Create test settings with temporary content directory."""
    return get_test_settings_with_content_path(temp_content_dir)


@pytest.fixture
def override_settings(test_settings):
    """Override app settings dependency."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield test_settings
    app.dependency_overrides.clear()


class TestCalculateReadingTime:
    """Tests for calculate_reading_time function."""

    def test_short_content(self):
        """Test reading time for short content is at least 1 minute."""
        content = "Hello world"
        assert calculate_reading_time(content) == 1

    def test_medium_content(self):
        """Test reading time for medium content."""
        # 200 words should be ~1 minute at 200 wpm
        content = " ".join(["word"] * 200)
        assert calculate_reading_time(content) == 1

    def test_long_content(self):
        """Test reading time for longer content."""
        # 600 words should be ~3 minutes at 200 wpm
        content = " ".join(["word"] * 600)
        assert calculate_reading_time(content) == 3

    def test_very_long_content(self):
        """Test reading time for very long content."""
        # 1000 words should be 5 minutes at 200 wpm
        content = " ".join(["word"] * 1000)
        assert calculate_reading_time(content) == 5

    def test_empty_content(self):
        """Test reading time for empty content is at least 1 minute."""
        content = ""
        assert calculate_reading_time(content) == 1


class TestLoadPostFromPath:
    """Tests for load_post_from_path function."""

    def test_load_valid_post(self, temp_content_dir):
        """Test loading a valid post."""
        post_path = Path(temp_content_dir) / "posts" / "test-post-1" / "README.md"
        metadata = load_post_from_path(post_path, "test-post-1")

        assert metadata is not None
        assert metadata.title == "Test Post 1"
        assert metadata.slug == "test-post-1"
        assert metadata.description == "This is the first test post about Python programming."
        assert metadata.author == "Test Author"
        assert "python" in metadata.tags
        assert "testing" in metadata.tags
        assert metadata.published is True
        assert metadata.reading_time_minutes >= 1

    def test_load_unpublished_post_returns_none(self, temp_content_dir):
        """Test loading an unpublished post returns None."""
        post_path = Path(temp_content_dir) / "posts" / "unpublished-post" / "README.md"
        metadata = load_post_from_path(post_path, "unpublished-post")

        assert metadata is None

    def test_load_nonexistent_post_returns_none(self, temp_content_dir):
        """Test loading a nonexistent post returns None."""
        post_path = Path(temp_content_dir) / "posts" / "nonexistent" / "README.md"
        metadata = load_post_from_path(post_path, "nonexistent")

        assert metadata is None


class TestGetAllPosts:
    """Tests for get_all_posts function."""

    def test_get_all_published_posts(self, test_settings):
        """Test getting all published posts."""
        posts = get_all_posts(test_settings)

        # Should include 4 published posts (2 folder-based + 1 legacy + 1 related)
        assert len(posts) == 4

        # Verify all posts are published
        for post in posts:
            assert post.published is True

        # Verify unpublished post is not included
        slugs = [p.slug for p in posts]
        assert "unpublished-post" not in slugs

    def test_posts_sorted_by_date_descending(self, test_settings):
        """Test posts are sorted by date in descending order."""
        posts = get_all_posts(test_settings)

        # Posts should be sorted newest to oldest
        dates = [p.date for p in posts if p.date]
        assert dates == sorted(dates, reverse=True)

    def test_folder_based_structure(self, test_settings):
        """Test that folder-based posts are loaded correctly."""
        posts = get_all_posts(test_settings)
        slugs = [p.slug for p in posts]

        assert "test-post-1" in slugs
        assert "test-post-2" in slugs

    def test_flat_structure_legacy(self, test_settings):
        """Test that flat .md files are loaded correctly."""
        posts = get_all_posts(test_settings)
        slugs = [p.slug for p in posts]

        assert "legacy-post" in slugs


class TestFindPostFile:
    """Tests for find_post_file function."""

    def test_find_folder_based_post(self, temp_content_dir):
        """Test finding a folder-based post."""
        posts_dir = Path(temp_content_dir) / "posts"
        result = find_post_file(posts_dir, "test-post-1")

        assert result is not None
        assert result.name == "README.md"
        assert "test-post-1" in str(result)

    def test_find_flat_structure_post(self, temp_content_dir):
        """Test finding a flat-structure post."""
        posts_dir = Path(temp_content_dir) / "posts"
        result = find_post_file(posts_dir, "legacy-post")

        assert result is not None
        assert result.name == "legacy-post.md"

    def test_find_nonexistent_post(self, temp_content_dir):
        """Test finding a nonexistent post returns None."""
        posts_dir = Path(temp_content_dir) / "posts"
        result = find_post_file(posts_dir, "nonexistent-post")

        assert result is None


class TestMatchesSearch:
    """Tests for matches_search function."""

    def test_search_by_title(self):
        """Test searching by title."""
        post = PostMetadata(
            title="Python Programming Guide",
            slug="python-guide",
            description="A guide to Python",
            tags=["programming"],
        )

        assert matches_search(post, "Python") is True
        assert matches_search(post, "python") is True  # Case insensitive
        assert matches_search(post, "Guide") is True
        assert matches_search(post, "JavaScript") is False

    def test_search_by_description(self):
        """Test searching by description."""
        post = PostMetadata(
            title="Tutorial",
            slug="tutorial",
            description="Learn web development with React",
            tags=["web"],
        )

        assert matches_search(post, "React") is True
        assert matches_search(post, "web development") is True
        assert matches_search(post, "Vue") is False

    def test_search_by_tags(self):
        """Test searching by tags."""
        post = PostMetadata(
            title="API Guide",
            slug="api-guide",
            description="Building APIs",
            tags=["fastapi", "python", "rest"],
        )

        assert matches_search(post, "fastapi") is True
        assert matches_search(post, "rest") is True
        assert matches_search(post, "graphql") is False

    def test_multi_keyword_search(self):
        """Test multi-keyword search (AND logic)."""
        post = PostMetadata(
            title="Python API Tutorial",
            slug="python-api",
            description="Building REST APIs with Python",
            tags=["python", "api"],
        )

        # All terms must match
        assert matches_search(post, "Python API") is True
        assert matches_search(post, "Python REST") is True
        assert matches_search(post, "Python GraphQL") is False  # GraphQL not found

    def test_partial_matching(self):
        """Test partial word matching."""
        post = PostMetadata(
            title="Performance Testing",
            slug="performance-testing",
            description="Load testing best practices",
            tags=["testing", "performance"],
        )

        assert matches_search(post, "perform") is True
        assert matches_search(post, "test") is True
        assert matches_search(post, "load") is True

    def test_search_with_none_description(self):
        """Test search when description is None."""
        post = PostMetadata(
            title="Simple Post",
            slug="simple",
            tags=["test"],
        )

        assert matches_search(post, "Simple") is True
        assert matches_search(post, "test") is True


class TestListPostsEndpoint:
    """Tests for GET /api/posts endpoint."""

    @pytest.mark.asyncio
    async def test_list_posts_success(self, override_settings):
        """Test listing posts with valid API key."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert "total" in data
        assert data["total"] == 4  # 4 published posts

    @pytest.mark.asyncio
    async def test_list_posts_without_api_key(self, override_settings):
        """Test listing posts without API key returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/posts")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_posts_with_invalid_api_key(self, override_settings):
        """Test listing posts with invalid API key returns 403."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                headers={"X-API-Key": "invalid-key"},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_posts_with_tag_filter(self, override_settings):
        """Test filtering posts by tag."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                params={"tag": "python"},
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        # test-post-1, legacy-post, and related-post have python tag
        assert data["total"] == 3
        for post in data["posts"]:
            assert "python" in [t.lower() for t in post["tags"]]

    @pytest.mark.asyncio
    async def test_list_posts_with_search_query(self, override_settings):
        """Test searching posts."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                params={"q": "JavaScript"},
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        # test-post-2 should match
        slugs = [p["slug"] for p in data["posts"]]
        assert "test-post-2" in slugs

    @pytest.mark.asyncio
    async def test_list_posts_with_multi_keyword_search(self, override_settings):
        """Test multi-keyword search."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                params={"q": "python testing"},
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        # Should match posts with both "python" AND "testing"
        for post in data["posts"]:
            searchable = f"{post['title']} {post.get('description', '')} {' '.join(post['tags'])}".lower()
            assert "python" in searchable
            assert "testing" in searchable

    @pytest.mark.asyncio
    async def test_list_posts_with_tag_and_search(self, override_settings):
        """Test combining tag filter and search."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                params={"tag": "api", "q": "Test Post 1"},
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        # Only test-post-1 should match (has api tag and matches search)
        assert data["total"] == 1
        assert data["posts"][0]["slug"] == "test-post-1"


class TestListTagsEndpoint:
    """Tests for GET /api/posts/tags endpoint."""

    @pytest.mark.asyncio
    async def test_list_tags_success(self, override_settings):
        """Test listing all tags."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/tags",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert "total" in data

        # Verify expected tags are present
        tags = data["tags"]
        assert "python" in tags
        assert "testing" in tags
        assert "javascript" in tags
        assert "api" in tags

    @pytest.mark.asyncio
    async def test_list_tags_sorted_alphabetically(self, override_settings):
        """Test tags are sorted alphabetically (case-insensitive)."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/tags",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        tags = data["tags"]

        # Verify sorted
        assert tags == sorted(tags, key=str.lower)

    @pytest.mark.asyncio
    async def test_list_tags_without_api_key(self, override_settings):
        """Test listing tags without API key returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/posts/tags")

        assert response.status_code == 401


class TestGetPostEndpoint:
    """Tests for GET /api/posts/{slug} endpoint."""

    @pytest.mark.asyncio
    async def test_get_post_success(self, override_settings):
        """Test getting a single post by slug."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-1",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Post 1"
        assert data["slug"] == "test-post-1"
        assert "content" in data
        assert "html_content" in data
        assert data["reading_time_minutes"] >= 1

    @pytest.mark.asyncio
    async def test_get_post_html_content(self, override_settings):
        """Test post HTML content is rendered."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-1",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        # HTML should contain paragraph tags
        assert "<p>" in data["html_content"]

    @pytest.mark.asyncio
    async def test_get_post_not_found(self, override_settings):
        """Test getting nonexistent post returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/nonexistent-slug",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_post_folder_based(self, override_settings):
        """Test getting a folder-based post."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-2",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        assert response.json()["slug"] == "test-post-2"

    @pytest.mark.asyncio
    async def test_get_post_flat_structure(self, override_settings):
        """Test getting a flat-structure (legacy) post."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/legacy-post",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        assert response.json()["slug"] == "legacy-post"

    @pytest.mark.asyncio
    async def test_get_post_without_api_key(self, override_settings):
        """Test getting post without API key returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/posts/test-post-1")

        assert response.status_code == 401


class TestRelatedPostsEndpoint:
    """Tests for GET /api/posts/{slug}/related endpoint."""

    @pytest.mark.asyncio
    async def test_get_related_posts_success(self, override_settings):
        """Test getting related posts."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-1/related",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert "total" in data

        # Should not include the current post
        slugs = [p["slug"] for p in data["posts"]]
        assert "test-post-1" not in slugs

    @pytest.mark.asyncio
    async def test_related_posts_by_shared_tags(self, override_settings):
        """Test related posts prioritize shared tags."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-1/related",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()

        # related-post shares python and testing tags with test-post-1
        # It should be in the related posts
        slugs = [p["slug"] for p in data["posts"]]
        assert "related-post" in slugs

    @pytest.mark.asyncio
    async def test_related_posts_with_limit(self, override_settings):
        """Test limiting related posts count."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-1/related",
                params={"limit": 2},
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) <= 2

    @pytest.mark.asyncio
    async def test_related_posts_not_found(self, override_settings):
        """Test related posts for nonexistent post returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/nonexistent-slug/related",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_related_posts_without_api_key(self, override_settings):
        """Test getting related posts without API key returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/posts/test-post-1/related")

        assert response.status_code == 401


class TestReadingTimeIntegration:
    """Integration tests for reading time calculation in posts."""

    @pytest.mark.asyncio
    async def test_reading_time_in_post_list(self, override_settings):
        """Test reading time is included in post list."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        for post in data["posts"]:
            assert "reading_time_minutes" in post
            assert post["reading_time_minutes"] >= 1

    @pytest.mark.asyncio
    async def test_reading_time_in_single_post(self, override_settings):
        """Test reading time is included in single post."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/test-post-1",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert "reading_time_minutes" in data
        assert data["reading_time_minutes"] >= 1


class TestWithRealContent:
    """Tests using the actual tayzhang-posts content."""

    @pytest.fixture
    def real_content_settings(self):
        """Create settings pointing to actual content."""
        real_content_path = "/Users/yuxzhang/Workspace/taylorzhang/github/tayzhang-app/tayzhang-posts"
        return Settings(
            content_repo_path=real_content_path,
            api_key=TEST_API_KEY,
        )

    @pytest.fixture
    def override_real_settings(self, real_content_settings):
        """Override app settings with real content path."""
        app.dependency_overrides[get_settings] = lambda: real_content_settings
        yield real_content_settings
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_real_posts(self, override_real_settings):
        """Test listing real posts from tayzhang-posts."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0

        # Verify some expected posts exist
        slugs = [p["slug"] for p in data["posts"]]
        # Check for a known post slug
        assert any("performance" in slug for slug in slugs)

    @pytest.mark.asyncio
    async def test_get_real_post(self, override_real_settings):
        """Test getting a specific real post."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/2022-12-11-performance-testing-load-testing",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert "performance" in data["title"].lower()
        assert "content" in data
        assert len(data["content"]) > 0

    @pytest.mark.asyncio
    async def test_real_tags_list(self, override_real_settings):
        """Test listing tags from real posts."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts/tags",
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        # Check for some expected tags
        tags_lower = [t.lower() for t in data["tags"]]
        assert "performance" in tags_lower or "python" in tags_lower or "career" in tags_lower

    @pytest.mark.asyncio
    async def test_search_real_posts(self, override_real_settings):
        """Test searching real posts."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/posts",
                params={"q": "performance"},
                headers={"X-API-Key": TEST_API_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
