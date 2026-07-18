"""Seed hospitals + doctors from Flora Medical Tourism PDF profile forms."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timezone

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import async_session_factory
from app.models.doctor import Doctor, DoctorAvailability, DoctorSpecialization
from app.models.hospital import Hospital
from app.models.user import User
from app.utils.enums import UserRole

DEFAULT_PASSWORD = "Doctor@123456"


def weekday_availability(start: str, end: str) -> list[dict]:
    sh, sm, ss = map(int, start.split(":"))
    eh, em, es = map(int, end.split(":"))
    return [
        {
            "day_of_week": d,
            "start_time": time(sh, sm, ss),
            "end_time": time(eh, em, es),
            "is_available": True,
            "slot_duration_minutes": 30,
            "max_appointments": 8,
        }
        for d in range(0, 6)
    ]


HOSPITALS = [
    {
        "key": "skin_n_smile",
        "name": "Skin N Smile Klinic",
        "slug": "skin-n-smile-klinic",
        "description": "Dermatology and dental clinic specializing in skin, hair transplant, and aesthetic procedures.",
        "email": "drdoisns@gmail.com",
        "phone": "+919104044040",
        "website": "https://www.skinnsmileklinic.com",
        "address_line1": "Shree Parshva Orion, 305/6/7, beside Adani Gas Station, Paldi Cross Roads",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
    },
    {
        "key": "cheers",
        "name": "Cheers Multi Speciality Hospital",
        "slug": "cheers-multi-speciality-hospital",
        "description": "Multi-speciality hospital offering orthopedics, spine surgery, neurosurgery, gynecology, fertility & IVF, general surgery, urology, and respiratory medicine.",
        "email": "Info.amd@cheershospitals.com",
        "phone": "+919998818148",
        "website": "https://www.cheershospitals.com",
        "address_line1": "Swapneel-5, Near Commerce Six Roads, Navrangpura",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "380009",
    },
    {
        "key": "fusion",
        "name": "Fusion Kidney Institute",
        "slug": "fusion-kidney-institute",
        "description": "Specialized kidney institute focused on urology, renal transplantation, and minimally invasive urological surgeries.",
        "email": "info@fusionkidney.com",
        "address_line1": "Fusion Kidney Institute, Ahmedabad",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
    },
    {
        "key": "orthosport",
        "name": "OrthoSport Hospital",
        "slug": "orthosport-hospital",
        "description": "Orthopaedic hospital specializing in joint replacement, sports injuries, and arthroscopy.",
        "email": "contact@verddaan.com",
        "phone": "9090080505",
        "address_line1": "Opp Prahladnagar Fire Station, near YMCA Club",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
    },
    {
        "key": "firozji",
        "name": "Firozji Physiotherapist Clinic",
        "slug": "firozji-physiotherapist-clinic",
        "description": "Physiotherapy clinic offering neuro, orthopaedic, post-surgery, pregnancy, and weight-loss physiotherapy care.",
        "email": "DRFARHAN_PIRZADA@YAHOO.COM",
        "phone": "9974305501",
        "address_line1": "L1, L2 Al-Burooj Commercial, Opp. Seventh Heaven, Makarba",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "380055",
    },
    {
        "key": "nova",
        "name": "Nova IVF Wings Women's Hospital",
        "slug": "nova-ivf-wings-womens-hospital",
        "description": "Women's hospital and IVF centre offering fertility treatments including IVF, ICSI, PGT, and related reproductive procedures.",
        "email": "pushpak.jhaveri@novaivffertility.com",
        "phone": "+917600848484",
        "website": "https://www.novaivffertility.com/ivf-centre/ahmedabad/fertility-clinic-bodakdev",
        "address_line1": "17, Sunrise Park, Himalaya Mall to Vastrapur Lake Road, Bodakdev",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "380054",
    },
]


DOCTORS = [
    {
        "hospital_key": "skin_n_smile",
        "email": "drdoisns@gmail.com",
        "full_name": "Dr. Shadab R. Doi",
        "phone": "+919104044040",
        "title": "Dr.",
        "primary_specialty": "Dermatologist & Hair Transplant Surgeon",
        "years_of_experience": 9,
        "qualifications": ["MBBS", "MD DVL", "FIAL", "Fellow Hair Transplant"],
        "education": [
            {"degree": "MBBS", "college": "VNSGU", "year": 2016, "location": "Surat, India"},
            {"degree": "MD DVL", "college": "Gujarat University", "year": 2020, "location": "Ahmedabad, India"},
            {"degree": "FIAL", "college": "ASI", "year": 2021, "location": "Melbourne, Australia"},
        ],
        "certifications": [
            {"name": "Fellowship in Aesthetic & Laser Medicine", "location": "Australia"},
            {"name": "Fellowship in Hair Transplantation", "location": "Istanbul, Turkey"},
        ],
        "bio": (
            "Dr. Shadab Doi is a Consultant Dermatologist, Dermatosurgeon, Hair Transplant Surgeon, "
            "and Aesthetic Physician with over 9 years of clinical experience. Key expertise includes "
            "acne scar treatment, vitiligo surgery, anti-ageing procedures, hair transplantation, and "
            "advanced laser dermatology."
        ),
        "languages_spoken": ["English", "Hindi", "Gujarati"],
        "consultation_fee": 700.0,
        "address_line1": "Shree Parshva Orion, 305/6/7, beside Adani Gas Station, Paldi Cross Roads",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "specializations": [
            ("Dermatology", True),
            ("Hair Transplant", False),
            ("Aesthetic Dermatology", False),
        ],
        "availability": weekday_availability("10:30:00", "18:30:00"),
    },
    {
        "hospital_key": "cheers",
        "email": "shiraz.munshi@cheershospitals.com",
        "full_name": "Dr. Shiraz Ahmed Munshi",
        "phone": "+919998818148",
        "title": "Dr.",
        "primary_specialty": "Endoscopic Spine Surgery & Pain Management",
        "years_of_experience": 16,
        "qualifications": ["MBBS", "D.Ortho", "DNB", "FIPP (USA)"],
        "education": [
            {"degree": "MBBS", "college": "BJMC Ahmedabad", "year": 2003, "location": "India"},
            {"degree": "DNB – Anesthesia", "college": "National Board", "year": 2008, "location": "India"},
            {"degree": "Diploma – Orthopedics", "college": "CPS Maharashtra", "year": 2018, "location": "India"},
            {"degree": "FIPP", "year": 2008, "location": "USA"},
        ],
        "certifications": [
            {"name": "FIPP - Fellow of Interventional Pain Practice", "location": "World Institute of Pain, USA"},
            {"name": "Fellow Selective Endoscopic Discectomy", "location": "DISC, Phoenix-Arizona, USA"},
        ],
        "bio": (
            "Pioneer of Interventional Pain and Spine Endoscopy in India and East Africa. "
            "Motto: 'No One should Live with Pain, No one should Die of Pain'. Offers pain management, "
            "endoscopic spine surgery, and regenerative therapy."
        ),
        "languages_spoken": ["English", "Hindi", "Gujarati", "Arabic", "Swahili"],
        "consultation_fee": 2000.0,
        "address_line1": "Swapneel-5, Near Commerce Six Roads, Navrangpura",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "380009",
        "specializations": [
            ("Pain Management", True),
            ("Endoscopic Spine Surgery", False),
            ("Regenerative Therapy", False),
        ],
        "availability": weekday_availability("12:00:00", "20:00:00"),
    },
    {
        "hospital_key": "fusion",
        "email": "manish.dhawan@fusionkidney.com",
        "full_name": "Dr. Manish Dhawan",
        "title": "Dr.",
        "primary_specialty": "Urology & Kidney Transplant",
        "years_of_experience": 10,
        "qualifications": ["MBBS", "MS", "DNB"],
        "education": [
            {"degree": "MBBS", "college": "Medical College"},
            {"degree": "MS (General Surgery)", "college": "Medical College"},
            {"degree": "DNB (Urology)", "college": "National Board of Examinations"},
        ],
        "certifications": [
            {"name": "DNB Urology"},
            {"name": "Renal Transplant Surgery"},
        ],
        "bio": (
            "Urologist and Kidney Transplant Surgeon and Director at Fusion Kidney Institute, Ahmedabad. "
            "Specializes in urology, renal transplantation, and minimally invasive urological surgeries."
        ),
        "languages_spoken": ["English", "Hindi", "Gujarati"],
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "specializations": [
            ("Kidney Transplant", True),
            ("Minimally Invasive Urology", False),
            ("Renal Surgery", False),
            ("Endourology", False),
        ],
        "availability": weekday_availability("09:00:00", "17:00:00"),
    },
    {
        "hospital_key": "orthosport",
        "email": "pranjel.pipara@orthosport.com",
        "full_name": "Dr. Pranjel Pipara",
        "phone": "9090080505",
        "title": "Dr.",
        "primary_specialty": "Joint Replacement & Sports Injuries",
        "years_of_experience": 18,
        "qualifications": ["MBBS", "MS Ortho"],
        "education": [
            {"degree": "MBBS", "college": "KMC Mangalore", "year": "2002-2008", "location": "India"},
            {"degree": "MS Ortho", "college": "MS Ramaiah Medical College", "year": "2008-2011", "location": "Bangalore, India"},
        ],
        "certifications": [
            {"name": "ISAKOS Fellow"},
            {"name": "Fellowship in Joint Replacement and Sports Injury", "location": "Vienna"},
        ],
        "bio": (
            "Expertise in shoulder and knee surgery including joint replacement and sports injury/"
            "arthroscopy. In private practice in Ahmedabad since 2011. 16,000+ procedures."
        ),
        "languages_spoken": ["English", "Hindi", "Gujarati", "Arabic"],
        "address_line1": "Opp Prahladnagar Fire Station, near YMCA Club",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "specializations": [
            ("Joint Replacement", True),
            ("Sports Injury & Arthroscopy", False),
            ("Orthopaedics", False),
        ],
        "availability": weekday_availability("09:00:00", "17:00:00"),
    },
    {
        "hospital_key": "firozji",
        "email": "DRFARHAN_PIRZADA@YAHOO.COM",
        "full_name": "Dr. Farhanahmed F. Pirzada",
        "phone": "9974305501",
        "title": "Dr.",
        "primary_specialty": "Physiotherapist",
        "years_of_experience": 25,
        "qualifications": ["B.PT"],
        "education": [
            {"degree": "Bachelor in Physiotherapy", "college": "Rajiv Gandhi College", "year": 1996, "location": "Mangalore, India"},
        ],
        "certifications": [
            {"name": "B.PT"},
            {"name": "IAP"},
            {"name": "USA PT License (LARA)"},
        ],
        "bio": (
            "Practicing since 2001. Treats orthopaedic, neuro, post-surgery, and pregnancy-related "
            "physiotherapy cases. HOD at Firozji Physiotherapist Clinic, Makarba, Ahmedabad."
        ),
        "languages_spoken": ["English", "Hindi", "Gujarati"],
        "video_consultation_enabled": True,
        "chat_consultation_enabled": False,
        "in_person_enabled": True,
        "address_line1": "L1, L2 Al-Burooj Commercial, Opp. Seventh Heaven, Makarba",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "380055",
        "specializations": [
            ("Physiotherapy", True),
            ("Neuro Physiotherapy", False),
            ("Orthopaedic Physiotherapy", False),
            ("Post Surgery Rehabilitation", False),
        ],
        "availability": weekday_availability("10:00:00", "22:00:00"),
    },
    {
        "hospital_key": "nova",
        "email": "jayesh.amin@novaivffertility.com",
        "full_name": "Dr. Jayesh Amin",
        "phone": "+917600848484",
        "title": "Dr.",
        "primary_specialty": "In Vitro Fertilization",
        "years_of_experience": 25,
        "qualifications": ["MBBS", "MD (Gynaecology)"],
        "education": [
            {"degree": "MBBS", "college": "Saurashtra University", "year": 2000, "location": "India"},
            {"degree": "MD (Obstetrics & Gynaecology)", "college": "Saurashtra University", "year": 2003, "location": "India"},
        ],
        "certifications": [
            {"name": "Fellowship for IVF & Embryology", "location": "LARS Johnson, Sweden"},
        ],
        "bio": (
            "Senior Consultant with more than 25 years of experience and 30,000+ IVF pregnancies. "
            "Successfully treated 10,000+ patients with PGT-A and trained more than 250 gynecologists "
            "to become IVF specialists."
        ),
        "languages_spoken": ["English", "Hindi", "Gujarati"],
        "consultation_fee": 2000.0,
        "address_line1": "17, Sunrise Park, Himalaya Mall to Vastrapur Lake Road, Bodakdev",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "380054",
        "specializations": [
            ("In Vitro Fertilization", True),
            ("Reproductive Endocrinology", False),
        ],
        "availability": weekday_availability("10:00:00", "18:00:00"),
    },
]


async def get_or_create_hospital(db, data: dict, admin_id) -> Hospital:
    result = await db.execute(
        select(Hospital).where(
            Hospital.slug == data["slug"],
            Hospital.is_deleted == False,
        )
    )
    hospital = result.scalar_one_or_none()
    if hospital:
        print(f"EXISTS hospital: {hospital.name} ({hospital.id})")
        return hospital

    hospital = Hospital(
        name=data["name"],
        slug=data["slug"],
        description=data.get("description"),
        email=data.get("email"),
        phone=data.get("phone"),
        website=data.get("website"),
        address_line1=data["address_line1"],
        city=data["city"],
        state=data.get("state"),
        country=data["country"],
        postal_code=data.get("postal_code"),
        is_active=True,
        created_by=admin_id,
    )
    db.add(hospital)
    await db.flush()
    print(f"CREATED hospital: {hospital.name} ({hospital.id})")
    return hospital


async def create_doctor(db, data: dict, hospital: Hospital, admin_id) -> None:
    email = data["email"]
    existing_user = await db.execute(
        select(User).where(User.email == email, User.is_deleted == False)
    )
    if existing_user.scalar_one_or_none():
        print(f"SKIP doctor (email exists): {data['full_name']} <{email}>")
        return

    user = User(
        email=email,
        hashed_password=get_password_hash(DEFAULT_PASSWORD),
        full_name=data["full_name"],
        phone=data.get("phone"),
        role=UserRole.DOCTOR.value,
        is_active=True,
        is_verified=True,
        verification_token=None,
        created_by=admin_id,
    )
    db.add(user)
    await db.flush()

    doctor = Doctor(
        user_id=user.id,
        hospital_id=hospital.id,
        title=data.get("title"),
        primary_specialty=data.get("primary_specialty"),
        years_of_experience=data.get("years_of_experience"),
        qualifications=data.get("qualifications"),
        education=data.get("education"),
        certifications=data.get("certifications"),
        bio=data.get("bio"),
        languages_spoken=data.get("languages_spoken"),
        consultation_fee=data.get("consultation_fee"),
        consultation_duration_minutes=data.get("consultation_duration_minutes", 30),
        video_consultation_enabled=data.get("video_consultation_enabled", True),
        chat_consultation_enabled=data.get("chat_consultation_enabled", True),
        in_person_enabled=data.get("in_person_enabled", True),
        address_line1=data.get("address_line1"),
        city=data.get("city"),
        state=data.get("state"),
        country=data.get("country"),
        postal_code=data.get("postal_code"),
        is_verified=True,
        verification_date=datetime.now(timezone.utc),
        created_by=admin_id,
    )
    db.add(doctor)
    await db.flush()

    for name, is_primary in data.get("specializations", []):
        db.add(
            DoctorSpecialization(
                doctor_id=doctor.id,
                specialization=name,
                is_primary=is_primary,
                created_by=admin_id,
            )
        )

    for avail in data.get("availability", []):
        db.add(
            DoctorAvailability(
                doctor_id=doctor.id,
                created_by=admin_id,
                **avail,
            )
        )

    print(f"CREATED doctor: {user.full_name} -> {hospital.name} ({doctor.id})")


async def main() -> None:
    async with async_session_factory() as db:
        admin_result = await db.execute(
            select(User).where(
                User.email == "admin@medicaltourism.com",
                User.is_deleted == False,
            )
        )
        admin = admin_result.scalar_one_or_none()
        if not admin:
            raise SystemExit("Admin user admin@medicaltourism.com not found")

        hospital_map: dict[str, Hospital] = {}
        print("=== Hospitals ===")
        for h in HOSPITALS:
            hospital_map[h["key"]] = await get_or_create_hospital(db, h, admin.id)

        print("\n=== Doctors ===")
        for d in DOCTORS:
            hospital = hospital_map[d["hospital_key"]]
            await create_doctor(db, d, hospital, admin.id)

        await db.commit()
        print("\nDone. Default doctor password:", DEFAULT_PASSWORD)


if __name__ == "__main__":
    asyncio.run(main())
