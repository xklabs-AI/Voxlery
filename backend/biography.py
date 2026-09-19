"""
Tagged Entity Biography and Search Engine using Gemma 4 E4B.
Compiles photo descriptions, dates, places, and companion bonds into comprehensive
life biographies and answers natural language questions about specific people and pets.
"""

import json
import urllib.request
import urllib.error
from typing import Optional

from backend.config import OLLAMA_HOST
from backend.db import (
    get_conn, get_person_by_id, get_entity_biography,
    upsert_entity_biography, get_people_for_photos,
)

PRIMARY_ENTITY_MODEL = "gemma4:e4b"
FALLBACK_ENTITY_MODEL = "gemma4:e2b"


def resolve_entity_model(model_name: Optional[str] = None) -> str:
    """Resolve preferred model with fallback."""
    candidate = (model_name or "").strip()
    if candidate:
        return candidate
    return PRIMARY_ENTITY_MODEL


def call_ollama(prompt: str, model: str = PRIMARY_ENTITY_MODEL, timeout: int = 120) -> str:
    """Call Ollama generation endpoint with error handling and fallback."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.65,
            "top_p": 0.9,
            "think": False,
            "num_predict": 1200,
        },
    }

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        # Fallback to e2b if e4b timed out or failed
        if model != FALLBACK_ENTITY_MODEL:
            try:
                payload["model"] = FALLBACK_ENTITY_MODEL
                req_fallback = urllib.request.Request(
                    f"{OLLAMA_HOST}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req_fallback, timeout=90) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("response", "").strip()
            except Exception:
                pass
        raise e


def fetch_entity_photos(person_id: int) -> tuple[dict, list[dict]]:
    """
    Fetch person profile and all photos featuring this person/pet,
    including companions, locations, and VLM descriptions.
    """
    with get_conn() as conn:
        person = get_person_by_id(conn, person_id)
        if not person:
            raise ValueError(f"Person {person_id} not found.")

        rows = conn.execute(
            """SELECT DISTINCT i.id, i.file_path, i.date_taken, i.place_name,
                               i.city, i.region, i.country, i.camera_make, i.camera_model,
                               i.raw_description, i.enriched_text
               FROM faces f
               JOIN images i ON f.image_id = i.id
               WHERE f.person_id = ?
               ORDER BY i.date_taken ASC, i.id ASC""",
            (person_id,),
        ).fetchall()

        photos = [dict(r) for r in rows]

        # Gather co-occurring companions for each photo
        if photos:
            photo_ids = [p["id"] for p in photos]
            companions_by_photo = get_people_for_photos(conn, photo_ids)
            for p in photos:
                others = [
                    c for c in companions_by_photo.get(p["id"], [])
                    if c.get("person_id") != person_id
                ]
                p["companions"] = others

        return person, photos


def format_dossier_text(person: dict, photos: list[dict], max_photos: int = 50) -> str:
    """Format chronological photo observations into structured text for Gemma 4."""
    name = person["name"]
    rel = person.get("relationship") or "Individual"
    notes = person.get("notes") or ""

    lines = [
        f"Subject Profile:",
        f"- Name: {name}",
        f"- Relationship / Entity Type: {rel}",
    ]
    if notes:
        lines.append(f"- Personal Notes: {notes}")
    lines.append(f"- Total Photo Records: {len(photos)}\n")
    lines.append(
        f"IMPORTANT CONTEXT: {name} is confirmed and tagged in every photo below. "
        f"When descriptions mention a {rel.lower()} (or matching person/pet/animal in the scene), that is {name}. "
        f"Synthesize their life story, activities, favorite spots, and companions from these observations.\n"
    )
    lines.append("Chronological Photo Observations from Library:")

    # Select representative photos across timeline if too many
    selected = photos
    if len(photos) > max_photos:
        step = len(photos) / max_photos
        selected = [photos[int(i * step)] for i in range(max_photos)]

    for idx, p in enumerate(selected, 1):
        dt = p.get("date_taken") or "Undated"
        loc = p.get("place_name") or (f"{p.get('city')}, {p.get('country')}" if p.get("city") else "Local setting")
        desc = (p.get("raw_description") or p.get("enriched_text") or "").strip()
        
        comps = ""
        if p.get("companions"):
            names = [f"{c['name']} ({c['relationship']})" for c in p["companions"]]
            comps = f" | Companions in photo: {', '.join(names)}"

        lines.append(f"Photo #{p['id']} [{dt} @ {loc}{comps}]:")
        lines.append(f"  {desc}\n")

    return "\n".join(lines)


def generate_entity_biography(
    person_id: int,
    model: str = PRIMARY_ENTITY_MODEL,
    force: bool = False,
) -> dict:
    """
    Generate or return cached comprehensive AI Biography / Life Profile
    synthesized by Gemma 4 E4B from photo archive descriptions.
    """
    model = resolve_entity_model(model)

    with get_conn() as conn:
        person = get_person_by_id(conn, person_id)
        if not person:
            raise ValueError(f"Person {person_id} not found.")

        # Check cache unless forced
        if not force:
            cached = get_entity_biography(conn, person_id)
            if cached and cached.get("biography"):
                return {
                    "status": "ok",
                    "person": person,
                    "biography": cached["biography"],
                    "model_used": cached.get("model_used", model),
                    "photo_count": cached.get("photo_count", 0),
                    "cached": True,
                    "updated_at": cached.get("updated_at"),
                }

    person, photos = fetch_entity_photos(person_id)
    if not photos:
        bio = f"No photos have been tagged for **{person['name']}** ({person.get('relationship', 'Individual')}) yet. Open photos from your library to tag faces or pets to build their biography."
        return {
            "status": "ok",
            "person": person,
            "biography": bio,
            "model_used": model,
            "photo_count": 0,
            "cached": False,
        }

    dossier = format_dossier_text(person, photos)
    is_pet = "pet" in (person.get("relationship") or "").lower()

    if is_pet:
        role_desc = "cherished family pet"
        prompt_specifics = (
            "Focus on their breed/appearance, favorite resting spots, play habits, interactions "
            "with toys/foods, family members they bond with, and personality quirks evident in the scenes."
        )
    else:
        role_desc = f"treasured {person.get('relationship', 'person').lower()}"
        prompt_specifics = (
            "Focus on their personality, personal style, places they've traveled, passions/hobbies, "
            "memorable moments, and bonds with companions who appear alongside them."
        )

    prompt = f"""You are an insightful, warm biographer and personal memory chronicler.
Below is an evidentiary dossier of photographic records from a private photo library for {person['name']}, a {role_desc}.

{dossier}

Instructions:
Write an authentic, heartwarming, and beautifully written biography and profile of {person['name']} strictly synthesized from the photo observations above.
Do NOT invent fake facts. Every insight should be rooted in the visual descriptions, places, and dates.
{prompt_specifics}

Please organize your biography using the following markdown headings:
### 🌟 Overview & Personality
A warm introduction capturing who {person['name']} is, their appearance, and character traits revealed through the photos.

### 🌍 Places & Environments
Where {person['name']} spends time — trips, natural landscapes, home spots, favorite settings.

### 🎨 Activities, Habits & Passions
Observed daily routines, favorite items/toys/foods, hobbies, sports, celebrations, and playful moments.

### 👥 Bonds & Companionship
Connections with other family members, friends, or fellow pets appearing across their photos.

### 📅 Archival Highlights
A concise chronological reflection of their memorable milestones across the years represented.

Write in evocative, natural prose with warmth and precision. Output only the biography in formatted markdown.
"""

    biography_text = call_ollama(prompt, model=model)

    # Cache result
    with get_conn() as conn:
        upsert_entity_biography(
            conn,
            person_id=person_id,
            biography=biography_text,
            model_used=model,
            photo_count=len(photos),
        )

    return {
        "status": "ok",
        "person": person,
        "biography": biography_text,
        "model_used": model,
        "photo_count": len(photos),
        "cached": False,
    }


def search_entity_info(
    person_id: int,
    query: str,
    model: str = PRIMARY_ENTITY_MODEL,
) -> dict:
    """
    Answer a specific search query or question about a tagged person/pet
    using Gemma 4 E4B by examining relevant photo descriptions.
    """
    model = resolve_entity_model(model)
    query_clean = (query or "").strip()
    if not query_clean:
        raise ValueError("Query string cannot be empty.")

    person, photos = fetch_entity_photos(person_id)
    if not photos:
        return {
            "status": "ok",
            "person": person,
            "query": query_clean,
            "answer": f"There are currently no tagged photos for {person['name']} in the library to answer this query.",
            "photos": [],
            "model_used": model,
        }

    # Score relevance of photos to the query
    q_words = set(query_clean.lower().split())
    scored_photos = []
    for p in photos:
        text = f"{p.get('place_name', '')} {p.get('date_taken', '')} {p.get('raw_description', '')} {p.get('enriched_text', '')}".lower()
        score = sum(1 for w in q_words if w in text and len(w) > 2)
        scored_photos.append((score, p))

    # Sort descending by relevance score, preserving chronology as secondary
    scored_photos.sort(key=lambda item: (item[0], item[1].get("date_taken") or ""), reverse=True)

    # Take top relevant photos (up to 16)
    top_photos = [item[1] for item in scored_photos[:16]]

    # Format relevant evidence
    evidence_lines = []
    for p in top_photos:
        dt = p.get("date_taken") or "Undated"
        loc = p.get("place_name") or "Local setting"
        desc = (p.get("raw_description") or p.get("enriched_text") or "").strip()
        comps = ""
        if p.get("companions"):
            names = [f"{c['name']} ({c['relationship']})" for c in p["companions"]]
            comps = f" | Companions: {', '.join(names)}"
        evidence_lines.append(f"Photo #{p['id']} [{dt} @ {loc}{comps}]:\n  {desc}\n")

    evidence_str = "\n".join(evidence_lines)

    prompt = f"""You are an intelligent personal photo archivist answering a question about {person['name']} ({person.get('relationship', 'Individual')}).
IMPORTANT CONTEXT: {person['name']} is confirmed to be the tagged {person.get('relationship', 'subject').lower()} in all the photographic records below. When descriptions mention a {person.get('relationship', 'person/pet').lower()} (such as a cat, dog, or person), that is {person['name']}.

Photographic Records:
{evidence_str}

User Question: "{query_clean}"

Instructions:
1. Answer the question directly, warmly, and helpfully based on the scenes and observations where {person['name']} is featured.
2. Mention specific dates, locations, companions, and observable details (toys, activities, food, spots) where relevant.
3. If a specific detail is not observed in the photos, state so gently.
4. Keep the answer structured, insightful, and concise (2-4 paragraphs).
"""

    answer_text = call_ollama(prompt, model=model)

    evidence = [
        {
            "photo_id": p["id"],
            "date": p.get("date_taken"),
            "place": p.get("place_name"),
            "description": p.get("raw_description") or p.get("enriched_text"),
            "companions": [c["name"] for c in p.get("companions", [])]
        }
        for p in top_photos
    ]

    return {
        "status": "ok",
        "person": person,
        "query": query_clean,
        "answer": answer_text,
        "photos": top_photos,
        "evidence": evidence,
        "model_used": model,
        "total_entity_photos": len(photos),
    }
