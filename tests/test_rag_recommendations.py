"""Tests for chatbot service recommendations and website-scope guardrails."""

import numpy as np
import pytest

from app.services.rag_service import (
    OUT_OF_SCOPE_PROMPT,
    SYSTEM_PROMPT,
    KnowledgeBase,
    RAGChatService,
)


@pytest.fixture
def service() -> RAGChatService:
    """RAGChatService without __init__ — avoids needing an OpenAI key."""
    return object.__new__(RAGChatService)


class FakeHotel:
    id = "11111111-1111-1111-1111-111111111111"
    name = "Grand Care Hotel"
    slug = "grand-care-hotel"
    description = "Comfortable rooms for patients and families."
    short_description = "Patient-friendly hotel beside the hospital."
    star_rating = 4
    city = "Ahmedabad"
    country = "India"
    amenities = ["WiFi", "Breakfast", "Airport pickup"]
    medical_amenities = ["Wheelchair access", "Nurse on call"]
    base_price_per_night = 3500.0
    currency = "INR"
    rating = 4.6
    total_reviews = 128
    distance_to_hospital_km = 0.8
    nearest_hospital = "Apollo Hospital"
    cover_image_url = "https://cdn.example.com/hotel.jpg"


class FakeApartment:
    id = "22222222-2222-2222-2222-222222222222"
    name = "Serenity Serviced Apartments"
    slug = "serenity-serviced-apartments"
    description = "Long-stay apartments with kitchen."
    short_description = "Two-bedroom apartments for extended recovery."
    bedroom_type = "2BR"
    property_type = "Entire home"
    capacity = 4
    city = "Ahmedabad"
    country = "India"
    amenities = ["Kitchen", "Laundry"]
    medical_amenities = ["Step-free entry"]
    price_per_night = 2800.0
    price_per_month = 60000.0
    currency = "INR"
    rating = 4.4
    total_reviews = 52
    distance_to_hospital_km = 1.5
    nearest_hospital = "Apollo Hospital"
    cover_image_url = None


# ── Knowledge base text builders ──────────────────────────────


def test_hotel_text_includes_hospital_distance_and_price():
    text = KnowledgeBase()._hotel_to_text(FakeHotel())
    assert "Grand Care Hotel" in text
    assert "0.8 km away" in text
    assert "Apollo Hospital" in text
    assert "3500.0 per night" in text
    assert "accommodation" in text


def test_apartment_text_mentions_long_stay_and_monthly_rate():
    text = KnowledgeBase()._apartment_to_text(FakeApartment())
    assert "Serenity Serviced Apartments" in text
    assert "long stay" in text
    assert "2BR" in text
    assert "Monthly rate" in text


def test_site_pages_cover_the_service_sections():
    urls = {p["profile_url"] for p in KnowledgeBase()._site_pages()}
    assert {"/hotels", "/apartments", "/restaurants", "/packages", "/doctors", "/hospitals"} <= urls


def test_site_pages_are_all_site_relative():
    for page in KnowledgeBase()._site_pages():
        assert page["profile_url"].startswith("/"), page["profile_url"]
        assert page["type"] == "page"


# ── Scope gate ────────────────────────────────────────────────


def test_best_score_is_zero_for_empty_knowledge_base():
    assert KnowledgeBase().best_score(np.array([1.0, 0.0], dtype=np.float32)) == 0.0


def test_best_score_finds_the_closest_document():
    kb = KnowledgeBase()
    kb.embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    kb.documents = [{"type": "hotel"}, {"type": "doctor"}]
    score = kb.best_score(np.array([1.0, 0.0], dtype=np.float32))
    assert score == pytest.approx(1.0, abs=1e-5)


def test_search_returns_nothing_below_threshold():
    kb = KnowledgeBase()
    kb.embeddings = np.array([[1.0, 0.0]], dtype=np.float32)
    kb.documents = [{"type": "hotel", "name": "X"}]
    assert kb.search(np.array([0.0, 1.0], dtype=np.float32), threshold=0.3) == []


def test_in_scope_message_uses_the_full_prompt(service):
    messages = service._build_messages([], "Find me a hotel", "1. **X** — Hotel", "", in_scope=True)
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_out_of_scope_message_swaps_the_prompt(service):
    messages = service._build_messages([], "Who won the world cup?", "", "", in_scope=False)
    assert messages[0]["content"] == OUT_OF_SCOPE_PROMPT


def test_empty_context_in_scope_gets_an_explicit_do_not_invent_instruction(service):
    messages = service._build_messages([], "Find a cardiologist", "", "", in_scope=True)
    joined = " ".join(m["content"] for m in messages if m["role"] == "system")
    assert "Do not invent" in joined


def test_out_of_scope_does_not_get_an_empty_context_block(service):
    messages = service._build_messages([], "Write me a poem", "", "", in_scope=False)
    assert len(messages) == 2  # system prompt + user message only
    assert messages[-1]["role"] == "user"


def test_system_prompt_forbids_inventing_links():
    assert "Never guess or construct a URL" in SYSTEM_PROMPT
    assert "OUT OF SCOPE" in SYSTEM_PROMPT


# ── RAG context rendering ─────────────────────────────────────


def test_rag_context_renders_hotels_with_links(service):
    docs = [{
        "type": "hotel", "name": "Grand Care Hotel", "city": "Ahmedabad", "country": "India",
        "star_rating": 4, "rating": 4.6, "price": 3500, "currency": "INR",
        "distance_to_hospital_km": 0.8, "nearest_hospital": "Apollo Hospital",
        "profile_url": "/hotels/grand-care-hotel",
    }]
    context = service._build_rag_context(docs)
    assert "[View Hotel](/hotels/grand-care-hotel)" in context
    assert "0.8 km from Apollo Hospital" in context
    assert "INR 3500 per night" in context


def test_rag_context_renders_apartments_and_pages(service):
    docs = [
        {"type": "apartment", "name": "Serenity", "bedroom_type": "2BR", "capacity": 4,
         "city": "Ahmedabad", "country": "India", "profile_url": "/apartments/serenity"},
        {"type": "page", "name": "Hotels", "profile_url": "/hotels",
         "text": "Website page: Hotels (/hotels). Book hotel accommodation near hospitals."},
    ]
    context = service._build_rag_context(docs)
    assert "[View Apartment](/apartments/serenity)" in context
    assert "[Hotels](/hotels)" in context


def test_rag_context_omits_missing_price_and_distance(service):
    docs = [{"type": "hotel", "name": "Budget Inn", "city": "Delhi", "country": "India",
             "profile_url": "/hotels/budget-inn"}]
    context = service._build_rag_context(docs)
    assert "None" not in context
    assert "[View Hotel](/hotels/budget-inn)" in context


# ── Recommendations ───────────────────────────────────────────


def test_recommendations_exclude_doctors(service):
    docs = [
        {"type": "doctor", "id": "d1", "name": "Dr. A", "profile_url": "/doctors/d1"},
        {"type": "hotel", "id": "h1", "name": "Hotel A", "profile_url": "/hotels/a"},
    ]
    recs = service._extract_recommendations(docs)
    assert [r["type"] for r in recs] == ["hotel"]


def test_recommendations_are_ordered_by_service_type(service):
    docs = [
        {"type": "page", "id": None, "name": "Hotels", "profile_url": "/hotels", "text": "Website page: Hotels (/hotels). Browse."},
        {"type": "hospital", "id": "x", "name": "Apollo", "profile_url": "/hospitals/apollo"},
        {"type": "hotel", "id": "h1", "name": "Hotel A", "profile_url": "/hotels/a"},
        {"type": "apartment", "id": "a1", "name": "Apt A", "profile_url": "/apartments/a"},
    ]
    assert [r["type"] for r in service._extract_recommendations(docs)] == [
        "hotel", "apartment", "hospital", "page",
    ]


def test_recommendation_line_leads_with_hospital_distance(service):
    line = service._recommendation_line({
        "type": "hotel", "distance_to_hospital_km": 0.8, "nearest_hospital": "Apollo Hospital",
        "star_rating": 4, "rating": 4.6,
    })
    assert line.startswith("0.8 km from Apollo Hospital")
    assert "4-star" in line
    assert "rated 4.6/5" in line


def test_recommendation_line_is_none_without_usable_detail(service):
    assert service._recommendation_line({"type": "hotel"}) is None


def test_recommendations_carry_a_usable_url(service):
    docs = [{"type": "hotel", "id": "h1", "name": "Hotel A", "price": 3500,
             "currency": "INR", "profile_url": "/hotels/a", "relevance_score": 0.81}]
    rec = service._extract_recommendations(docs)[0]
    assert rec["url"] == "/hotels/a"
    assert rec["price"] == 3500
    assert rec["relevance_score"] == 0.81
