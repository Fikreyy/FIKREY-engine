import os
import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DATA_FILE = "baza_odcinkow.json"

def pobierz_xml(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()

def analizuj_odcinek_gemini(tytul, opis, kraj):
    if not GEMINI_API_KEY:
        return {
            "sponsorzy": "Brak",
            "kody_rabatowe": "-",
            "typ_monetyzacji": "Brak danych",
            "brand_safety_score": 100,
            "profil_odbiorcy": "N/A",
            "tone_of_voice": "N/A",
            "streszczenie": "Brak klucza API"
        }
    
    prompt = f"""Przeanalizuj odcinek podcastu (Kraj: {kraj}, Tytul: "{tytul}").
Opis: {opis[:2500]}

Zwroc WYLACZNIE prawidlowy obiekt JSON (bez znacznikow markdown, bez ```json):
{{
  "sponsorzy": "nazwy wykrytych sponsorow lub Brak",
  "kody_rabatowe": "kody i linki lub -",
  "typ_monetyzacji": "Sponsoring / Afiliacja / Autopromocja / Brak",
  "brand_safety_score": 95,
  "profil_odbiorcy": "krotki profil widowni",
  "tone_of_voice": "styl wypowiedzi",
  "streszczenie": "maksymalnie 2 zdania"
}}"""

    url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=){GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tekst = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(tekst)
    except Exception as e:
        print(f"Blad Gemini: {e}")
        return {
            "sponsorzy": "Brak danych",
            "kody_rabatowe": "-",
            "typ_monetyzacji": "-",
            "brand_safety_score": 100,
            "profil_odbiorcy": "-",
            "tone_of_voice": "-",
            "streszczenie": "Blad analizy"
        }

def main():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            baza = json.load(f)
    else:
        baza = []

    znane_guidy = {wpis.get("guid") for wpis in baza if "guid" in wpis}

    with open("podcasty.json", "r", encoding="utf-8") as f:
        katalog = json.load(f)

    nowe_wpisy = []

    for pod in katalog:
        nazwa = pod["nazwa"]
        rss_url = pod["rss"]
        kraj = pod["kraj"]
        kategoria = pod.get("kategoria", "Ogolna")

        print(f"Sprawdzam: {nazwa}")
        try:
            xml_data = pobierz_xml(rss_url)
            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                continue

            item = channel.find("item")
            if item is None:
                continue

            tytul = item.findtext("title") or "Bez tytulu"
            pub_date = item.findtext("pubDate") or ""
            guid = item.findtext("guid") or tytul
            opis = item.findtext("description") or ""

            if guid not in znane_guidy:
                print(f"--> Nowy odcinek: {tytul}")
                analiza = analizuj_odcinek_gemini(tytul, opis, kraj)
                
                nowy_rekord = {
                    "kraj": kraj,
                    "kategoria": kategoria,
                    "podcast": nazwa,
                    "tytul": tytul,
                    "data": pub_date,
                    "guid": guid,
                    "sponsorzy": analiza.get("sponsorzy", "Brak"),
                    "kody_rabatowe": analiza.get("kody_rabatowe", "-"),
                    "typ_monetyzacji": analiza.get("typ_monetyzacji", "-"),
                    "brand_safety_score": analiza.get("brand_safety_score", 100),
                    "profil_odbiorcy": analiza.get("profil_odbiorcy", "-"),
                    "tone_of_voice": analiza.get("tone_of_voice", "-"),
                    "streszczenie": analiza.get("streszczenie", "-"),
                    "zaktualizowano": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
                nowe_wpisy.append(nowy_rekord)
                znane_guidy.add(guid)

        except Exception as e:
            print(f"Blad przy {nazwa}: {e}")

    if nowe_wpisy:
        wszystkie = nowe_wpisy + baza
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(wszystkie, f, ensure_ascii=False, indent=2)
        print(f"Zapisano {len(nowe_wpisy)} nowych odcinkow.")
    else:
        print("Brak nowych odcinkow.")

if __name__ == "__main__":
    main()
