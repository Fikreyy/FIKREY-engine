import os
import json
import re
import xml.etree.ElementTree as ET
import urllib.request
from datetime import datetime
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
DATA_FILE = "baza_odcinkow.json"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

def pobierz_xml(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()

def analizuj_odcinek_gemini(tytul, opis, kraj):
    if not model:
        print("Brak aktywnego modelu Gemini API.")
        return {
            "sponsorzy": "Brak",
            "kody_rabatowe": "-",
            "typ_monetyzacji": "Organiczny",
            "brand_safety_score": 95,
            "profil_odbiorcy": "Biznes / Ogolny",
            "tone_of_voice": "Ekspercki",
            "streszczenie": tytul
        }

    prompt = f"""Przeanalizuj ponizszy odcinek podcastu pod katem komercyjnym i wizerunkowym.
Kraj: {kraj}
Tytul: {tytul}
Opis: {opis[:3000]}

Zwroc wylacznie czysty obiekt JSON (bez markdowna, bez ```json):
{{
  "sponsorzy": "nazwa wykrytej marki/sponsora lub 'Brak'",
  "kody_rabatowe": "kod znizkowy lub dedykowany link lub '-'",
  "typ_monetyzacji": "Sponsoring / Afiliacja / Autopromocja / Brak",
  "brand_safety_score": 95,
  "profil_odbiorcy": "profil sluchaczy np. Przedsiebiorcy, Inwestorzy",
  "tone_of_voice": "styl wypowiedzi np. Merytoryczny, Dynamiczny",
  "streszczenie": "maksymalnie 2 zdania podsumowania"
}}"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        print(f"Blad analizy Gemini dla '{tytul}': {e}")
        return {
            "sponsorzy": "Brak",
            "kody_rabatowe": "-",
            "typ_monetyzacji": "Organiczny",
            "brand_safety_score": 90,
            "profil_odbiorcy": "Ogolny",
            "tone_of_voice": "Informacyjny",
            "streszczenie": tytul
        }

def main():
    baza = []
    with open("podcasty.json", "r", encoding="utf-8") as f:
        katalog = json.load(f)

    for pod in katalog:
        nazwa = pod["nazwa"]
        rss_url = pod["rss"]
        kraj = pod.get("kraj", "PL")
        kategoria = pod.get("kategoria", "Biznes")

        print(f"Pobieram: {nazwa}")
        try:
            xml_data = pobierz_xml(rss_url)
            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                continue

            # Pobieramy 2 najnowsze odcinki
            for item in channel.findall("item")[:2]:
                tytul = item.findtext("title") or "Bez tytulu"
                pub_date = item.findtext("pubDate") or ""
                guid = item.findtext("guid") or tytul
                opis = item.findtext("description") or ""

                print(f"--> Gemini analizuje: {tytul}")
                analiza = analizuj_odcinek_gemini(tytul, opis, kraj)

                rekord = {
                    "kraj": kraj,
                    "kategoria": kategoria,
                    "podcast": nazwa,
                    "tytul": tytul,
                    "data": pub_date,
                    "guid": guid,
                    "sponsorzy": analiza.get("sponsorzy", "Brak"),
                    "kody_rabatowe": analiza.get("kody_rabatowe", "-"),
                    "typ_monetyzacji": analiza.get("typ_monetyzacji", "-"),
                    "brand_safety_score": analiza.get("brand_safety_score", 95),
                    "profil_odbiorcy": analiza.get("profil_odbiorcy", "-"),
                    "tone_of_voice": analiza.get("tone_of_voice", "-"),
                    "streszczenie": analiza.get("streszczenie", "-"),
                    "zaktualizowano": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
                baza.append(rekord)
        except Exception as e:
            print(f"Blad kanalu {nazwa}: {e}")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(baza, f, ensure_ascii=False, indent=2)
    print(f"Sukces: zapisano {len(baza)} odcinkow.")

if __name__ == "__main__":
    main()
