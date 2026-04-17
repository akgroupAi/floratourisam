"""RAG chatbot service — OpenAI embeddings + GPT-4o-mini.

Architecture:
  1. Knowledge base is built from doctors, hospitals, treatments in DB
  2. Each record is embedded via text-embedding-3-small and stored in a FAISS index
  3. User messages are embedded → top-K similar docs retrieved → fed as context to GPT-4o-mini
  4. Medical reports are parsed by GPT to extract conditions → matched to doctors
  5. Responses include clickable doctor/hospital links
"""

import base64
import io
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import numpy as np
from openai import AsyncOpenAI
from PyPDF2 import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.ai_log import AIConversation, AILog
from app.models.doctor import Doctor, DoctorSpecialization
from app.models.hospital import Hospital, Department
from app.models.user import User
from app.models.site import Treatment
from app.models.knowledge_document import KnowledgeDocument

logger = get_logger(__name__)

# ── Singleton vector store (rebuilt on demand) ────────────────


class KnowledgeBase:
    """In-memory vector store for RAG retrieval."""

    def __init__(self):
        self.embeddings: Optional[np.ndarray] = None  # (N, dim) float32
        self.documents: list[dict] = []  # parallel list of metadata
        self.is_built = False
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if not self._client:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not configured")
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts via OpenAI."""
        response = await self.client.embeddings.create(
            input=texts,
            model=settings.OPENAI_EMBEDDING_MODEL,
        )
        return np.array([d.embedding for d in response.data], dtype=np.float32)

    async def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text."""
        arr = await self.embed_texts([text])
        return arr[0]

    def search(self, query_vec: np.ndarray, top_k: int = 5, threshold: float = 0.3) -> list[dict]:
        """Cosine-similarity search over the knowledge base."""
        if self.embeddings is None or len(self.documents) == 0:
            return []

        # Normalise for cosine similarity
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        doc_norms = self.embeddings / (
            np.linalg.norm(self.embeddings, axis=1, keepdims=True) + 1e-10
        )
        similarities = doc_norms @ query_norm

        top_idx = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_idx:
            score = float(similarities[idx])
            if score < threshold:
                break
            doc = {**self.documents[idx], "relevance_score": round(score, 4)}
            results.append(doc)
        return results

    async def build_from_db(self, db: AsyncSession) -> None:
        """Build the knowledge base from database records."""
        documents: list[dict] = []
        texts: list[str] = []

        # ── Doctors ───────────────────────────────────────────
        doctor_rows = await db.execute(
            select(Doctor, User).join(User, Doctor.user_id == User.id).where(
                Doctor.is_deleted == False,
            )
        )
        for doctor, user in doctor_rows.all():
            specialties = []
            spec_result = await db.execute(
                select(DoctorSpecialization).where(
                    DoctorSpecialization.doctor_id == doctor.id
                )
            )
            for spec in spec_result.scalars().all():
                specialties.append(spec.specialization)

            # Build hospital name
            hospital_name = None
            if doctor.hospital_id:
                h_result = await db.execute(
                    select(Hospital.name).where(Hospital.id == doctor.hospital_id)
                )
                hospital_name = h_result.scalar_one_or_none()

            text = self._doctor_to_text(doctor, user, specialties, hospital_name)
            texts.append(text)
            documents.append({
                "type": "doctor",
                "id": str(doctor.id),
                "user_id": str(doctor.user_id),
                "name": f"{doctor.title or 'Dr.'} {user.full_name}".strip(),
                "specialty": doctor.primary_specialty or (specialties[0] if specialties else "General"),
                "specialties": specialties,
                "hospital": hospital_name,
                "city": doctor.city,
                "country": doctor.country,
                "rating": doctor.rating,
                "fee": doctor.consultation_fee,
                "experience_years": doctor.years_of_experience,
                "languages": doctor.languages_spoken or [],
                "photo_url": user.avatar_url,
                "profile_url": f"/doctors/{doctor.id}",
                "text": text,
            })

        # ── Hospitals ─────────────────────────────────────────
        hospital_rows = await db.execute(
            select(Hospital).where(
                Hospital.is_deleted == False,
                Hospital.is_active == True,
            )
        )
        for hospital in hospital_rows.scalars().all():
            text = self._hospital_to_text(hospital)
            texts.append(text)
            documents.append({
                "type": "hospital",
                "id": str(hospital.id),
                "name": hospital.name,
                "city": hospital.city,
                "country": hospital.country,
                "specialties": hospital.specialties or [],
                "rating": hospital.rating,
                "profile_url": f"/hospitals/{hospital.slug or hospital.id}",
                "text": text,
            })

        # ── Departments ───────────────────────────────────────
        dept_rows = await db.execute(
            select(Department, Hospital).join(
                Hospital, Department.hospital_id == Hospital.id
            ).where(Department.is_deleted == False)
        )
        for dept, hospital in dept_rows.all():
            text = self._department_to_text(dept, hospital)
            texts.append(text)
            documents.append({
                "type": "department",
                "id": str(dept.id),
                "name": dept.name,
                "hospital": hospital.name,
                "profile_url": f"/hospitals/{hospital.slug or hospital.id}",
                "text": text,
            })

        # ── Treatments ────────────────────────────────────────
        treatment_rows = await db.execute(
            select(Treatment).where(Treatment.is_deleted == False)
        )
        for treatment in treatment_rows.scalars().all():
            text = self._treatment_to_text(treatment)
            texts.append(text)
            documents.append({
                "type": "treatment",
                "id": str(treatment.id),
                "name": treatment.name,
                "slug": getattr(treatment, "slug", None),
                "profile_url": f"/treatments/{getattr(treatment, 'slug', treatment.id)}",
                "text": text,
            })

        # ── Admin knowledge documents ─────────────────────────
        kd_rows = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.is_deleted == False,
                KnowledgeDocument.is_active == True,
            )
        )
        for kd in kd_rows.scalars().all():
            text = f"{kd.category}: {kd.title}. {kd.content}"
            if kd.summary:
                text += f" Summary: {kd.summary}"
            texts.append(text)
            documents.append({
                "type": "knowledge",
                "id": str(kd.id),
                "category": kd.category,
                "title": kd.title,
                "tags": kd.tags or [],
                "text": text,
            })

        # ── Platform info (static) ────────────────────────────
        platform_docs = self._platform_knowledge()
        for doc in platform_docs:
            texts.append(doc["text"])
            documents.append(doc)

        if not texts:
            logger.warning("knowledge_base_empty")
            self.is_built = True
            return

        # Embed all in batches of 100
        all_embeddings = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            emb = await self.embed_texts(batch)
            all_embeddings.append(emb)

        self.embeddings = np.vstack(all_embeddings)
        self.documents = documents
        self.is_built = True
        logger.info(
            "knowledge_base_built",
            total_docs=len(documents),
            embedding_dim=self.embeddings.shape[1],
        )

    # ── Text builders ─────────────────────────────────────────

    def _doctor_to_text(self, doctor, user, specialties: list, hospital_name: str | None) -> str:
        parts = [
            f"Doctor: {doctor.title or 'Dr.'} {user.full_name}",
            f"Specialty: {doctor.primary_specialty or 'General Medicine'}",
        ]
        if specialties:
            parts.append(f"All specialties: {', '.join(specialties)}")
        if hospital_name:
            parts.append(f"Hospital: {hospital_name}")
        if doctor.years_of_experience:
            parts.append(f"Experience: {doctor.years_of_experience} years")
        if doctor.qualifications:
            parts.append(f"Qualifications: {', '.join(doctor.qualifications)}")
        if doctor.bio:
            parts.append(f"About: {doctor.bio[:500]}")
        if doctor.languages_spoken:
            parts.append(f"Languages: {', '.join(doctor.languages_spoken)}")
        if doctor.city:
            location = doctor.city
            if doctor.country:
                location += f", {doctor.country}"
            parts.append(f"Location: {location}")
        if doctor.consultation_fee:
            parts.append(f"Consultation fee: ${doctor.consultation_fee}")
        consult_types = []
        if doctor.video_consultation_enabled:
            consult_types.append("video")
        if doctor.chat_consultation_enabled:
            consult_types.append("chat")
        if doctor.in_person_enabled:
            consult_types.append("in-person")
        if consult_types:
            parts.append(f"Consultation types: {', '.join(consult_types)}")
        if doctor.rating:
            parts.append(f"Rating: {doctor.rating}/5 ({doctor.total_reviews} reviews)")
        return ". ".join(parts)

    def _hospital_to_text(self, hospital) -> str:
        parts = [
            f"Hospital: {hospital.name}",
        ]
        if hospital.description:
            parts.append(f"About: {hospital.description[:500]}")
        if hospital.specialties:
            parts.append(f"Specialties: {', '.join(hospital.specialties)}")
        if hospital.accreditations:
            parts.append(f"Accreditations: {', '.join(hospital.accreditations)}")
        if hospital.city:
            loc = hospital.city
            if hospital.country:
                loc += f", {hospital.country}"
            parts.append(f"Location: {loc}")
        if hospital.rating:
            parts.append(f"Rating: {hospital.rating}/5")
        if hospital.facilities:
            parts.append(f"Facilities: {json.dumps(hospital.facilities)[:300]}")
        return ". ".join(parts)

    def _department_to_text(self, dept, hospital) -> str:
        parts = [f"Department: {dept.name} at {hospital.name}"]
        if hasattr(dept, "description") and dept.description:
            parts.append(f"About: {dept.description[:300]}")
        return ". ".join(parts)

    def _treatment_to_text(self, treatment) -> str:
        parts = [f"Treatment: {treatment.name}"]
        if hasattr(treatment, "description") and treatment.description:
            parts.append(f"Description: {treatment.description[:500]}")
        if hasattr(treatment, "category") and treatment.category:
            parts.append(f"Category: {treatment.category}")
        return ". ".join(parts)

    def _platform_knowledge(self) -> list[dict]:
        """Static knowledge about the Flora Medical platform."""
        docs = [
            {
                "type": "platform",
                "text": (
                    "Flora Medical Tourism is a platform that connects international patients "
                    "with world-class healthcare providers in India. We offer end-to-end "
                    "medical tourism services including doctor consultations (video, chat, "
                    "in-person), hospital bookings, hotel and apartment accommodations, "
                    "airport transfers, and post-treatment follow-ups. Patients can browse "
                    "doctors by specialty, view ratings and reviews, book consultations, "
                    "and receive treatment proposals with detailed cost breakdowns."
                ),
            },
            {
                "type": "platform",
                "text": (
                    "How to book a consultation on Flora Medical: "
                    "1) Browse doctors by specialty or search by condition. "
                    "2) View doctor profiles with qualifications, experience, fees, and reviews. "
                    "3) Check available time slots for your preferred doctor. "
                    "4) Book a consultation (video, chat, or in-person). "
                    "5) Receive confirmation with meeting link (for video calls). "
                    "6) After consultation, the doctor may send a treatment proposal. "
                    "7) Review and approve/reject the treatment proposal. "
                    "8) If approved, book travel, accommodation, and hospital stay."
                ),
            },
            {
                "type": "platform",
                "text": (
                    "Flora Medical services include: Medical consultations with board-certified "
                    "doctors, Treatment proposals with transparent cost breakdowns, Hospital "
                    "bookings at accredited facilities, Hotel and serviced apartment accommodations, "
                    "Restaurant and dining recommendations, Currency exchange (forex), "
                    "Document management for medical records, Real-time chat with doctors, "
                    "AI-assisted health guidance, Post-treatment follow-up care."
                ),
            },
        ]
        return docs


# Global singleton — rebuilt periodically or on demand
_knowledge_base = KnowledgeBase()


async def get_knowledge_base(db: AsyncSession) -> KnowledgeBase:
    """Return the knowledge base, building it if needed."""
    if not _knowledge_base.is_built:
        await _knowledge_base.build_from_db(db)
    return _knowledge_base


async def rebuild_knowledge_base(db: AsyncSession) -> int:
    """Force rebuild. Returns doc count."""
    global _knowledge_base
    _knowledge_base = KnowledgeBase()
    await _knowledge_base.build_from_db(db)
    return len(_knowledge_base.documents)


# ── RAG Chat Service ──────────────────────────────────────────


SYSTEM_PROMPT = """You are Flora Medical's AI health assistant. You help patients:
- Understand their medical conditions and treatment options
- Find the right doctors and hospitals on the Flora Medical platform
- Navigate the platform (booking consultations, uploading reports, etc.)
- Get information about treatments, costs, and travel logistics

RULES:
1. Be empathetic, clear, and concise.
2. When recommending doctors, ALWAYS include a link: [Dr. Name](/doctors/{doctor_id})
3. When recommending hospitals, include: [Hospital Name](/hospitals/{slug_or_id})
4. If the patient describes symptoms or shares a medical report, suggest relevant specialists.
5. Never provide definitive medical diagnoses — always recommend consulting a doctor.
6. Include practical next steps (e.g., "You can book a consultation with Dr. X by clicking the link below").
7. When you suggest a doctor for a consultation, add a call-to-action like:
   "👉 [Book Consultation with Dr. Name](/doctors/{doctor_id})"
8. If you don't know something, say so honestly and suggest contacting support.
9. Keep responses focused and under 400 words unless the user asks for detail.
10. Format responses in clean markdown with headers and bullet points when appropriate.
11. At the END of every response, add a section with exactly 3 follow-up questions the user might ask next.
    Format them as a JSON array on its own line, prefixed with "FOLLOW_UP_QUESTIONS:" like this:
    FOLLOW_UP_QUESTIONS: ["Question 1?", "Question 2?", "Question 3?"]
    These should be contextually relevant to the conversation and help guide the patient.
"""


class RAGChatService:
    """RAG-based chatbot using OpenAI embeddings + GPT-4o-mini."""

    def __init__(self, db: AsyncSession):
        self.db = db
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat(
        self,
        user_id: UUID,
        message: str,
        session_id: Optional[str] = None,
        context_type: Optional[str] = None,
        context_data: Optional[dict] = None,
        report_text: Optional[str] = None,
    ) -> dict:
        """Process a user message through the RAG pipeline."""
        start_time = time.time()

        # 1. Get or create conversation
        conversation = await self._get_or_create_conversation(
            user_id, session_id, context_type
        )

        # 2. Load conversation history (last 10 messages)
        history = await self._get_history(conversation.id)

        # 3. If report text provided, extract medical info
        report_context = ""
        if report_text:
            report_context = await self._parse_report(report_text)

        # 4. Retrieve relevant knowledge
        kb = await get_knowledge_base(self.db)
        search_query = message
        if report_context:
            search_query += f" {report_context}"
        query_vec = await kb.embed_single(search_query)
        relevant_docs = kb.search(
            query_vec,
            top_k=settings.RAG_TOP_K,
            threshold=settings.RAG_SIMILARITY_THRESHOLD,
        )

        # 5. Build context from retrieved docs
        rag_context = self._build_rag_context(relevant_docs)

        # 6. Build messages for GPT
        messages = self._build_messages(
            history, message, rag_context, report_context
        )

        # 7. Call GPT-4o-mini
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        ai_response = response.choices[0].message.content
        usage = response.usage

        elapsed_ms = int((time.time() - start_time) * 1000)

        # 8. Extract follow-up questions from response
        ai_text, follow_up_questions = self._extract_follow_ups(ai_response)

        # 9. Extract doctor suggestions from relevant docs
        doctor_suggestions = self._extract_doctor_suggestions(relevant_docs, ai_text)

        # 10. Log the interaction
        log = await self._log_interaction(
            conversation=conversation,
            user_id=user_id,
            user_message=message,
            ai_response=ai_text,
            model=settings.OPENAI_MODEL,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            elapsed_ms=elapsed_ms,
            relevant_docs=relevant_docs,
        )

        # 11. Auto-title the conversation on first message
        if (conversation.message_count or 0) <= 1 and not conversation.title:
            conversation.title = self._generate_title(message)
            await self.db.commit()

        return {
            "response": ai_text,
            "session_id": conversation.session_id,
            "conversation_id": str(conversation.id),
            "log_id": str(log.id),
            "doctor_suggestions": doctor_suggestions,
            "follow_up_questions": follow_up_questions,
            "tokens_used": usage.total_tokens if usage else 0,
            "response_time_ms": elapsed_ms,
        }

    async def parse_report_and_suggest(
        self, user_id: UUID, report_text: str, session_id: Optional[str] = None
    ) -> dict:
        """Parse a medical report and suggest relevant doctors."""
        start_time = time.time()

        # Extract medical conditions from report
        extract_response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a medical report parser. Extract the following from the report:\n"
                        "1. Primary diagnosis/condition\n"
                        "2. Secondary conditions\n"
                        "3. Recommended specialty (e.g., Cardiology, Orthopedics)\n"
                        "4. Urgency level (routine, soon, urgent)\n"
                        "5. Brief summary for patient\n\n"
                        "Respond in JSON format:\n"
                        '{"primary_condition": "...", "secondary_conditions": [...], '
                        '"recommended_specialty": "...", "urgency": "...", "summary": "..."}'
                    ),
                },
                {"role": "user", "content": report_text[:4000]},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        parsed_text = extract_response.choices[0].message.content
        try:
            # Try to parse JSON from the response
            json_start = parsed_text.find("{")
            json_end = parsed_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(parsed_text[json_start:json_end])
            else:
                parsed = {"summary": parsed_text, "recommended_specialty": "General Medicine"}
        except json.JSONDecodeError:
            parsed = {"summary": parsed_text, "recommended_specialty": "General Medicine"}

        # Search for matching doctors
        kb = await get_knowledge_base(self.db)
        search_text = (
            f"{parsed.get('primary_condition', '')} "
            f"{parsed.get('recommended_specialty', '')} "
            f"{' '.join(parsed.get('secondary_conditions', []))}"
        )
        query_vec = await kb.embed_single(search_text)
        relevant_docs = kb.search(query_vec, top_k=8, threshold=0.25)

        doctors = [
            {
                "id": doc["id"],
                "name": doc["name"],
                "specialty": doc.get("specialty"),
                "specialties": doc.get("specialties", []),
                "hospital": doc.get("hospital"),
                "city": doc.get("city"),
                "rating": doc.get("rating"),
                "fee": doc.get("fee"),
                "experience_years": doc.get("experience_years"),
                "profile_url": doc["profile_url"],
                "relevance_score": doc.get("relevance_score"),
            }
            for doc in relevant_docs
            if doc["type"] == "doctor"
        ]

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "report_analysis": parsed,
            "recommended_doctors": doctors,
            "total_matches": len(doctors),
            "response_time_ms": elapsed_ms,
        }

    async def analyze_file(
        self,
        user_id: UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        session_id: Optional[str] = None,
        user_message: Optional[str] = None,
    ) -> dict:
        """Analyze an uploaded image (via GPT vision) or PDF (text extraction) and suggest doctors."""
        start_time = time.time()

        is_image = content_type.startswith("image/")
        is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")

        if not is_image and not is_pdf:
            raise ValueError("Unsupported file type. Upload an image (JPG/PNG) or PDF.")

        # ── Extract medical info from file ──
        if is_image:
            parsed = await self._analyze_image(file_bytes, content_type, user_message)
        else:
            pdf_text = self._extract_pdf_text(file_bytes)
            if not pdf_text or len(pdf_text.strip()) < 10:
                raise ValueError("Could not extract text from PDF. The file may be scanned/image-based.")
            parsed = await self._analyze_text_report(pdf_text)

        # ── Find matching doctors via RAG ──
        kb = await get_knowledge_base(self.db)
        search_text = (
            f"{parsed.get('primary_condition', '')} "
            f"{parsed.get('recommended_specialty', '')} "
            f"{' '.join(parsed.get('secondary_conditions', []))}"
        )
        query_vec = await kb.embed_single(search_text)
        relevant_docs = kb.search(query_vec, top_k=8, threshold=0.25)

        doctors = [
            {
                "id": doc["id"],
                "name": doc["name"],
                "specialty": doc.get("specialty"),
                "specialties": doc.get("specialties", []),
                "hospital": doc.get("hospital"),
                "city": doc.get("city"),
                "rating": doc.get("rating"),
                "fee": doc.get("fee"),
                "experience_years": doc.get("experience_years"),
                "profile_url": doc["profile_url"],
                "relevance_score": doc.get("relevance_score"),
            }
            for doc in relevant_docs
            if doc["type"] == "doctor"
        ]

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "file_type": "image" if is_image else "pdf",
            "filename": filename,
            "report_analysis": parsed,
            "recommended_doctors": doctors,
            "total_matches": len(doctors),
            "response_time_ms": elapsed_ms,
        }

    async def _analyze_image(
        self, image_bytes: bytes, content_type: str, user_message: Optional[str] = None
    ) -> dict:
        """Use GPT-4o-mini vision to analyze a medical image/report."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{content_type};base64,{b64}"

        prompt = (
            "You are a medical report/image analyzer. Analyze this medical document image and extract:\n"
            "1. Primary diagnosis/condition\n"
            "2. Secondary conditions\n"
            "3. Recommended medical specialty (e.g., Cardiology, Orthopedics)\n"
            "4. Urgency level (routine, soon, urgent)\n"
            "5. Brief summary for the patient\n\n"
            "Respond ONLY in JSON format:\n"
            '{"primary_condition": "...", "secondary_conditions": [...], '
            '"recommended_specialty": "...", "urgency": "...", "summary": "..."}'
        )
        if user_message:
            prompt += f"\n\nAdditional context from patient: {user_message}"

        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    ],
                }
            ],
            temperature=0.3,
            max_tokens=600,
        )

        parsed_text = response.choices[0].message.content
        return self._parse_json_response(parsed_text)

    async def _analyze_text_report(self, report_text: str) -> dict:
        """Analyze extracted PDF text using GPT."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a medical report parser. Extract the following from the report:\n"
                        "1. Primary diagnosis/condition\n"
                        "2. Secondary conditions\n"
                        "3. Recommended specialty (e.g., Cardiology, Orthopedics)\n"
                        "4. Urgency level (routine, soon, urgent)\n"
                        "5. Brief summary for patient\n\n"
                        "Respond ONLY in JSON format:\n"
                        '{"primary_condition": "...", "secondary_conditions": [...], '
                        '"recommended_specialty": "...", "urgency": "...", "summary": "..."}'
                    ),
                },
                {"role": "user", "content": report_text[:8000]},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        parsed_text = response.choices[0].message.content
        return self._parse_json_response(parsed_text)

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyPDF2."""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages_text = []
            for page in reader.pages[:20]:  # limit to 20 pages
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n".join(pages_text)
        except Exception as exc:
            logger.error("pdf_extraction_failed", error=str(exc))
            return ""

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from GPT response, with fallback."""
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except (json.JSONDecodeError, ValueError):
            pass
        return {"summary": text, "recommended_specialty": "General Medicine"}

    # ── Internal helpers ──────────────────────────────────────

    async def _get_or_create_conversation(
        self, user_id: UUID, session_id: Optional[str], context_type: Optional[str]
    ) -> AIConversation:
        if session_id:
            result = await self.db.execute(
                select(AIConversation).where(
                    AIConversation.session_id == session_id,
                    AIConversation.user_id == user_id,
                    AIConversation.is_active == True,
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        conv = AIConversation(
            user_id=user_id,
            session_id=session_id or str(uuid4()),
            context_type=context_type or "general",
            is_active=True,
        )
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def _get_history(self, conversation_id: UUID, limit: int = 10) -> list[dict]:
        result = await self.db.execute(
            select(AILog)
            .where(AILog.conversation_id == conversation_id)
            .order_by(AILog.created_at.desc())
            .limit(limit)
        )
        logs = list(reversed(result.scalars().all()))
        history = []
        for log in logs:
            history.append({"role": "user", "content": log.user_message})
            history.append({"role": "assistant", "content": log.ai_response})
        return history

    async def _parse_report(self, report_text: str) -> str:
        """Quick extraction of key medical terms from report text."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract key medical conditions, diagnoses, and recommended "
                            "specialties from this medical report. Return only a brief "
                            "comma-separated list of relevant medical terms and specialties."
                        ),
                    },
                    {"role": "user", "content": report_text[:4000]},
                ],
                temperature=0.2,
                max_tokens=200,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("report_parse_failed", error=str(exc))
            return ""

    def _build_rag_context(self, docs: list[dict]) -> str:
        if not docs:
            return ""
        parts = ["Here is relevant information from our platform:\n"]
        for i, doc in enumerate(docs, 1):
            if doc["type"] == "doctor":
                parts.append(
                    f"{i}. **{doc['name']}** — {doc.get('specialty', 'Specialist')}"
                    f" | {doc.get('hospital', 'N/A')}"
                    f" | Rating: {doc.get('rating', 'N/A')}"
                    f" | Fee: ${doc.get('fee', 'N/A')}"
                    f" | [View Profile]({doc['profile_url']})"
                )
            elif doc["type"] == "hospital":
                parts.append(
                    f"{i}. **{doc['name']}** — Hospital"
                    f" | {doc.get('city', '')}, {doc.get('country', '')}"
                    f" | Rating: {doc.get('rating', 'N/A')}"
                    f" | [View Details]({doc['profile_url']})"
                )
            elif doc["type"] == "treatment":
                parts.append(
                    f"{i}. Treatment: **{doc.get('name', 'N/A')}**"
                    f" | [Learn More]({doc.get('profile_url', '#')})"
                )
            elif doc["type"] == "platform":
                parts.append(f"{i}. {doc['text'][:300]}")
            else:
                parts.append(f"{i}. {doc.get('text', '')[:200]}")
        return "\n".join(parts)

    def _build_messages(
        self,
        history: list[dict],
        user_message: str,
        rag_context: str,
        report_context: str,
    ) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if rag_context:
            messages.append({
                "role": "system",
                "content": f"RETRIEVED CONTEXT:\n{rag_context}",
            })

        if report_context:
            messages.append({
                "role": "system",
                "content": f"MEDICAL REPORT ANALYSIS:\n{report_context}",
            })

        # Add conversation history
        messages.extend(history)

        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_suggestions(self, docs: list[dict], message: str) -> list[str]:
        suggestions = []
        has_doctors = any(d["type"] == "doctor" for d in docs)
        has_hospitals = any(d["type"] == "hospital" for d in docs)

        if has_doctors:
            suggestions.append("Book a consultation with a recommended doctor")
            suggestions.append("Compare doctor profiles and fees")
        if has_hospitals:
            suggestions.append("View hospital details and facilities")
        if not has_doctors:
            suggestions.append("Find a doctor for my condition")

        suggestions.append("Upload my medical report for analysis")
        suggestions.append("How do I book a consultation?")
        return suggestions[:5]

    def _extract_follow_ups(self, ai_response: str) -> tuple[str, list[str]]:
        """Extract FOLLOW_UP_QUESTIONS from GPT response and return (clean_text, questions)."""
        follow_ups = []
        clean_text = ai_response

        marker = "FOLLOW_UP_QUESTIONS:"
        idx = ai_response.find(marker)
        if idx != -1:
            clean_text = ai_response[:idx].rstrip()
            json_part = ai_response[idx + len(marker):].strip()
            try:
                json_start = json_part.find("[")
                json_end = json_part.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    follow_ups = json.loads(json_part[json_start:json_end])
            except (json.JSONDecodeError, ValueError):
                pass

        if not follow_ups:
            follow_ups = [
                "What treatments are available for my condition?",
                "How do I book a consultation?",
                "Can you help me find a specialist?",
            ]

        return clean_text, follow_ups[:5]

    def _extract_doctor_suggestions(self, docs: list[dict], ai_text: str) -> list[dict]:
        """Build rich doctor suggestion dicts from relevant docs."""
        suggestions = []
        for doc in docs:
            if doc["type"] != "doctor":
                continue
            # Generate a short recommendation line
            rec_parts = []
            if doc.get("rating") and doc["rating"] >= 4.5:
                rec_parts.append("Highly recommended specialist")
            elif doc.get("rating"):
                rec_parts.append("Excellent alternative")
            if doc.get("experience_years"):
                rec_parts.append(f"with {doc['experience_years']}+ years experience")
            if doc.get("rating"):
                rec_parts.append(f"and great reviews")
            recommendation = " ".join(rec_parts) + "." if rec_parts else None

            suggestions.append({
                "id": doc["id"],
                "name": doc["name"],
                "specialty": doc.get("specialty"),
                "specialties": doc.get("specialties", []),
                "hospital": doc.get("hospital"),
                "city": doc.get("city"),
                "country": doc.get("country"),
                "rating": doc.get("rating"),
                "fee": doc.get("fee"),
                "experience_years": doc.get("experience_years"),
                "languages": doc.get("languages", []),
                "photo_url": doc.get("photo_url"),
                "profile_url": doc["profile_url"],
                "recommendation": recommendation,
            })
        return suggestions

    def _generate_title(self, first_message: str) -> str:
        """Generate a short conversation title from the first user message."""
        title = first_message.strip()
        if len(title) > 60:
            title = title[:57].rsplit(" ", 1)[0] + "..."
        return title or "New chat"

    async def _log_interaction(
        self,
        conversation: AIConversation,
        user_id: UUID,
        user_message: str,
        ai_response: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        elapsed_ms: int,
        relevant_docs: list[dict],
    ) -> AILog:
        # Estimate cost (GPT-4o-mini pricing)
        cost = (prompt_tokens * 0.00015 + completion_tokens * 0.0006) / 1000

        log = AILog(
            conversation_id=conversation.id,
            user_id=user_id,
            user_message=user_message,
            ai_response=ai_response,
            system_prompt=SYSTEM_PROMPT[:500],
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time_ms=elapsed_ms,
            cost=cost,
            request_metadata={
                "relevant_docs_count": len(relevant_docs),
                "doc_types": [d["type"] for d in relevant_docs],
            },
        )
        self.db.add(log)

        # Update conversation stats
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.total_tokens_used = (conversation.total_tokens_used or 0) + total_tokens
        conversation.estimated_cost = (conversation.estimated_cost or 0) + cost

        await self.db.commit()
        await self.db.refresh(log)
        return log
