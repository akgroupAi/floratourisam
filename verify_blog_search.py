
import asyncio
import sys
from datetime import datetime

from app.db.session import async_session_factory
from app.models.site import BlogPost
from app.models.user import User

async def verify_blog_search():
    print("=== Verifying Blog Search API ===")
    
    async with async_session_factory() as db:
        try:
            # Cleanup previous run data
            from sqlalchemy import delete
            await db.execute(delete(BlogPost).where(BlogPost.slug.in_([
                "ai-in-healthcare-test", "heart-surgery-destinations-test", "healthy-eating-test"
            ])))
            await db.commit()

            # 1. Ensure we have a user for author
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.email == "test_blog_author@example.com"))
            user = result.scalar_one_or_none()
            
            if not user:
                print("Creating test user...")
                user = User(
                    email="test_blog_author@example.com",
                    full_name="Test Blog Author",
                    hashed_password="hashed_password",
                    is_active=True,
                )
                db.add(user)
                await db.flush()
            
            # 2. Create Test Blog Posts
            print("Creating test blog posts...")
            post1 = BlogPost(
                title="Understanding AI in Healthcare",
                slug="ai-in-healthcare-test",
                author_id=user.id,
                content="Artificial Intelligence is transforming medical diagnostics.",
                excerpt="AI diagnostics guide",
                category="Technology",
                status="published",
                published_at=datetime.utcnow()
            )
            
            post2 = BlogPost(
                title="Top 10 Destinations for Heart Surgery",
                slug="heart-surgery-destinations-test",
                author_id=user.id,
                content="India runs world-class cardiac programs.",
                excerpt="Cardiac care guide",
                category="Medical Tourism",
                status="published",
                published_at=datetime.utcnow()
            )
            
            post3 = BlogPost(
                title="Healthy Eating Habits",
                slug="healthy-eating-test",
                author_id=user.id,
                content="Eat more green vegetables for better health.",
                excerpt="Nutrition guide",
                category="Wellness",
                status="draft",  # Should not be found
                published_at=datetime.utcnow()
            )
            
            db.add(post1)
            db.add(post2)
            db.add(post3)
            await db.commit()
            
            # 3. Test Search
            from httpx import AsyncClient, ASGITransport
            from app.main import app
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                
                # Test 1: Search for "AI" (Should find post1)
                print("\nTest 1: Search for 'AI'")
                response = await client.get("/api/v1/pages/blog/search?q=AI")
                assert response.status_code == 200
                data = response.json()
                print(f"Found {data['total']} posts")
                assert data['total'] >= 1
                assert any(p['slug'] == "ai-in-healthcare-test" for p in data['items'])
                print("✓ Found 'AI' post")
                
                # Test 2: Search for "Cardiac"
                print("\nTest 2: Search for 'Cardiac'")
                response = await client.get("/api/v1/pages/blog/search?q=Cardiac")
                assert response.status_code == 200
                data = response.json()
                assert any(p['slug'] == "heart-surgery-destinations-test" for p in data['items'])
                print("✓ Found 'Cardiac' post")
                
                # Test 3: Search for "Nutrition" (Draft post)
                print("\nTest 3: Search for 'Nutrition' (Draft post)")
                response = await client.get("/api/v1/pages/blog/search?q=Nutrition")
                data = response.json()
                # We don't know if other posts exist, but OUR draft post should not be there
                assert not any(p['slug'] == "healthy-eating-test" for p in data['items'])
                print("✓ Draft post not found")
            
            # Cleanup
            print("\nCleaning up...")
            await db.execute(delete(BlogPost).where(BlogPost.slug.in_([
                "ai-in-healthcare-test", "heart-surgery-destinations-test", "healthy-eating-test"
            ])))
            await db.commit()
            
            print("\nAll Blog Search tests passed!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_blog_search())
