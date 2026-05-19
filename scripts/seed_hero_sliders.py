import asyncio
import sys
from pathlib import Path

# Add the project root to sys.path so we can import app
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.db.session import async_session_factory
from app.models.site import HeroSlider
from sqlalchemy import delete

async def seed_sliders():
    async with async_session_factory() as session:
        # Optionally clear existing
        await session.execute(delete(HeroSlider))
        
        sliders = [
            HeroSlider(
                title="Your Complete Journey for Premium Stays",
                highlight_text="AI-Powered Healthcare Journey",
                description="From treatment to accommodation and forex — we handle everything for your medical journey in India.",
                features=["AI-Matched Specialists", "Transparent Pricing", "End-to-End Support"],
                background_image="https://images.unsplash.com/photo-1586773860418-d37222d8fce3?auto=format&fit=crop&q=80&w=1200",
                badge_text="Featured Service",
                primary_cta_text="Start Treatment Plan →",
                primary_cta_url="/packages",
                secondary_cta_text="Talk to AI Assistant",
                secondary_cta_url="/chat",
                featured_service_title="Home Made Food",
                featured_service_description="Fresh home-cooked meals for patients",
                featured_service_image="https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&q=80&w=600",
                featured_service_url="/services/food",
                display_order=1,
                is_active=True
            ),
            HeroSlider(
                title="World-Class Medical Care in India",
                highlight_text="Top Specialists",
                description="Access to internationally accredited hospitals and highly experienced surgeons.",
                features=["JCI Accredited", "No Wait Times", "Dedicated Case Manager"],
                background_image="https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&q=80&w=1200",
                badge_text="Premium Care",
                primary_cta_text="Find a Doctor",
                primary_cta_url="/doctors",
                secondary_cta_text="Get a Free Quote",
                secondary_cta_url="/leads",
                featured_service_title="Advanced Surgery",
                featured_service_description="Robotic and minimally invasive procedures",
                featured_service_image="https://images.unsplash.com/photo-1551076805-e1869033e561?auto=format&fit=crop&q=80&w=600",
                featured_service_url="/services/surgery",
                display_order=2,
                is_active=True
            ),
            HeroSlider(
                title="Seamless Forex & Visa Assistance",
                highlight_text="Hassle-Free Travel",
                description="We assist with medical visa letters, forex exchange, and travel logistics.",
                features=["Visa Support", "Best Exchange Rates", "Airport Transfers"],
                background_image="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&q=80&w=1200",
                badge_text="Travel Easy",
                primary_cta_text="Explore Services",
                primary_cta_url="/services",
                secondary_cta_text="Contact Us",
                secondary_cta_url="/contact",
                featured_service_title="Forex Exchange",
                featured_service_description="Get local currency at the best rates",
                featured_service_image="https://images.unsplash.com/photo-1580519542036-ed47f3ae3c31?auto=format&fit=crop&q=80&w=600",
                featured_service_url="/forex",
                display_order=3,
                is_active=True
            ),
             HeroSlider(
                title="Comfortable Recovery Stays",
                highlight_text="Premium Accommodation",
                description="Partner hotels and apartments tailored for post-operative care and recovery.",
                features=["Wheelchair Accessible", "Medical Staff on Call", "Dietary Menus"],
                background_image="https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&q=80&w=1200",
                badge_text="Post-Op Care",
                primary_cta_text="View Hotels",
                primary_cta_url="/hotels",
                secondary_cta_text="View Apartments",
                secondary_cta_url="/apartments",
                featured_service_title="Luxury Recovery",
                featured_service_description="Peaceful environments for healing",
                featured_service_image="https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&q=80&w=600",
                featured_service_url="/services/accommodation",
                display_order=4,
                is_active=True
            ),
             HeroSlider(
                title="Holistic Wellness & Ayush",
                highlight_text="Traditional Healing",
                description="Combine modern medicine with traditional Ayurveda, Yoga, and wellness retreats.",
                features=["Ayurveda Centers", "Yoga Therapy", "Detox Programs"],
                background_image="https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&q=80&w=1200",
                badge_text="Wellness",
                primary_cta_text="Explore Wellness",
                primary_cta_url="/packages",
                secondary_cta_text="Read Blog",
                secondary_cta_url="/pages/blog",
                featured_service_title="Ayurvedic Retreat",
                featured_service_description="Rejuvenate your body and mind",
                featured_service_image="https://images.unsplash.com/photo-1507652313651-74ffdf227918?auto=format&fit=crop&q=80&w=600",
                featured_service_url="/services/ayush",
                display_order=5,
                is_active=True
            )
        ]
        
        for slider in sliders:
            session.add(slider)
        
        await session.commit()
        print(f"Successfully seeded {len(sliders)} hero sliders!")

if __name__ == "__main__":
    asyncio.run(seed_sliders())
