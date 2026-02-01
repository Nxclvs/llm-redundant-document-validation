# scripts/generate_test_data.py

import argparse
import json
import random
from pathlib import Path
from datetime import timedelta, datetime
from typing import Dict, Any, Tuple, List

import numpy as np

try:
    from faker import Faker
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Missing dependencies. Please run: pip install faker pillow numpy")
    raise


REPO_ROOT = Path(__file__).resolve().parents[1]
faker = Faker("de_DE")



# Helpers

def get_font(size: int = 15, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font or fallback to default."""
    try:
        font_name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(font_name, size)
    except IOError:
        return ImageFont.load_default()


def apply_scan_effects(img: Image.Image) -> Image.Image:
    """
    Simulates a realistic scan process.
    Applies: slight rotation, occasional blur, noise, occasional downsampling.
    """
    w, h = img.size

    angle = random.uniform(-1.5, 1.5)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor="white")

    if random.random() > 0.6:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 0.8)))

    img_array = np.array(img)
    noise_level = random.randint(5, 12)
    noise = np.random.normal(0, noise_level, img_array.shape)
    img_noisy = img_array + noise
    img_noisy = np.clip(img_noisy, 0, 255).astype("uint8")
    img = Image.fromarray(img_noisy)

    if random.random() > 0.4:
        new_w, new_h = int(w * 0.8), int(h * 0.8)
        img = img.resize((new_w, new_h), resample=Image.BILINEAR)
        img = img.resize((w, h), resample=Image.NEAREST)

    return img


def draw_header(draw: ImageDraw.ImageDraw, title: str, width: int):
    font_title = get_font(30, bold=True)
    draw.text((50, 40), title, fill="black", font=font_title)
    draw.line((50, 80, width - 50, 80), fill="black", width=2)


def ensure_dataset_folders(dataset_root: Path) -> Tuple[Path, Path]:
    docs_dir = dataset_root / "documents"
    gt_dir = dataset_root / "ground_truth"
    docs_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir, gt_dir


def save_as_png_and_json(
    img: Image.Image,
    data: Dict[str, Any],
    docs_dir: Path,
    gt_dir: Path,
    doc_type: str,
    prefix: str,
    index: int,
):
    """
    documents/<doc_type>/<prefix>_<index>.png
    ground_truth/<doc_type>/<prefix>_<index>.json
    """
    docs_type_dir = docs_dir / doc_type
    gt_type_dir = gt_dir / doc_type
    docs_type_dir.mkdir(parents=True, exist_ok=True)
    gt_type_dir.mkdir(parents=True, exist_ok=True)

    filename_base = f"{prefix}_{index:03d}"

    final_img = apply_scan_effects(img)

    png_path = docs_type_dir / f"{filename_base}.png"
    final_img.save(png_path, "PNG", optimize=True)

    json_path = gt_type_dir / f"{filename_base}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Generated: {doc_type}/{png_path.name}")



# Generators

def generate_urlaubsantrag(index: int, docs_dir: Path, gt_dir: Path):
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_label = get_font(18, bold=True)
    font_val = get_font(18, bold=False)

    start_date = faker.date_between(start_date="-1y", end_date="+1y")
    days = random.randint(1, 20)
    end_date = start_date + timedelta(days=days)

    # Values as printed:
    personalnummer = str(random.randint(10000, 99999))
    name = faker.name()
    abteilung = random.choice(["IT", "HR", "Vertrieb", "Logistik"])
    art = random.choice(["Erholungsurlaub", "Sonderurlaub", "Bildungsurlaub"])
    von = start_date.strftime("%d.%m.%Y")
    bis = end_date.strftime("%d.%m.%Y")

    data = {
        "typ": "urlaubsantrag",
        "personalnummer": personalnummer,
        "name": name,
        "abteilung": abteilung,
        "art": art,
        "von": von,
        "bis": bis,
        "tage": days,
    }

    draw_header(draw, "URLAUBSANTRAG", width)

    y = 120
    fields = [
        ("Personalnummer:", personalnummer),
        ("Name, Vorname:", name),
        ("Abteilung:", abteilung),
        ("Urlaubsart:", art),
        ("Vom:", von),
        ("Bis:", bis),
        ("Anzahl Tage:", str(days)),
    ]

    for label, val in fields:
        draw.text((50, y), label, fill="black", font=font_label)
        draw.text((300, y), val, fill="darkblue", font=font_val)
        draw.line((300, y + 25, 700, y + 25), fill="gray", width=1)
        y += 60

    y += 50
    datum_print = faker.date_this_year().strftime("%d.%m.%Y")
    draw.text((50, y), f"Datum: {datum_print}", fill="black", font=font_val)
    draw.text((400, y), "Unterschrift:", fill="black", font=font_val)
    draw.text((400, y + 40), "(gez. Arbeitnehmer)", fill="darkblue", font=get_font(16))

    
    save_as_png_and_json(img, data, docs_dir, gt_dir, "urlaubsantrag", "REQ", index)


def generate_rechnung(index: int, docs_dir: Path, gt_dir: Path):
    width, height = 800, 1100
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_reg = get_font(16)
    font_bold = get_font(16, bold=True)

    company = faker.company()
    client = faker.name()
    inv_date = faker.date_this_year()
    inv_num = f"RE-{inv_date.year}-{random.randint(1000, 9999)}"

    
    sender_block = f"{company}\nMusterstraße 1\n12345 Musterstadt"
    empfaenger_block = f"{client}\n{faker.street_address()}\n{faker.postcode()} {faker.city()}"

    items: List[Dict[str, Any]] = []
    total_net = 0.0
    for pos in range(1, random.randint(2, 6) + 1):
        qty = random.randint(1, 10)
        price = round(random.uniform(10.0, 150.0), 2)
        line_total = round(qty * price, 2)
        total_net = round(total_net + line_total, 2)
        items.append(
            {
                "pos": pos,
                "beschreibung": faker.bs().capitalize(),
                "menge": qty,
                "einzelpreis": price,
                "gesamtpreis": line_total,
            }
        )

    vat = round(total_net * 0.19, 2)
    total_gross = round(total_net + vat, 2)

    datum = inv_date.strftime("%d.%m.%Y")

    data = {
        "typ": "rechnung",
        "sender": sender_block,
        "empfaenger": empfaenger_block,
        "rechnungsnummer": inv_num,
        "datum": datum,
        "items": items,
        "total_net": total_net,
        "total_vat": vat,
        "total_gross": total_gross,
    }

    draw_header(draw, company, width)
    draw.text((50, 100), f"Absender: {sender_block}", fill="gray", font=font_reg)
    draw.text((50, 180), f"Empfänger:\n{empfaenger_block}", fill="black", font=font_reg)
    draw.text((500, 180), f"Rechnungs-Nr: {inv_num}", fill="black", font=font_bold)
    draw.text((500, 210), f"Datum: {datum}", fill="black", font=font_reg)

    y = 350
    headers = ["Pos", "Beschreibung", "Menge", "Einzel (€)", "Gesamt (€)"]
    x_pos = [50, 100, 450, 550, 680]

    for i, h in enumerate(headers):
        draw.text((x_pos[i], y), h, fill="black", font=font_bold)
    draw.line((50, y + 25, 750, y + 25), fill="black", width=2)

    y += 40
    for item in items:
        draw.text((x_pos[0], y), str(item["pos"]), fill="black", font=font_reg)
        draw.text((x_pos[1], y), item["beschreibung"][:40], fill="black", font=font_reg)
        draw.text((x_pos[2], y), str(item["menge"]), fill="black", font=font_reg)
        draw.text((x_pos[3], y), f'{item["einzelpreis"]:.2f}', fill="black", font=font_reg)
        draw.text((x_pos[4], y), f'{item["gesamtpreis"]:.2f}', fill="black", font=font_reg)
        y += 30

    draw.line((400, y + 20, 750, y + 20), fill="black", width=1)
    y += 40

    draw.text((550, y), "Netto:", fill="black", font=font_reg)
    draw.text((680, y), f"{total_net:.2f} €", fill="black", font=font_reg)
    y += 25
    draw.text((550, y), "MwSt (19%):", fill="black", font=font_reg)
    draw.text((680, y), f"{vat:.2f} €", fill="black", font=font_reg)
    y += 30
    draw.text((550, y), "GESAMT:", fill="black", font=font_bold)
    draw.text((680, y), f"{total_gross:.2f} €", fill="black", font=font_bold)

    save_as_png_and_json(img, data, docs_dir, gt_dir, "rechnung", "INV", index)


def generate_bescheid(index: int, docs_dir: Path, gt_dir: Path):
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_reg = get_font(16)
    font_bold = get_font(16, bold=True)

    stadt = faker.city()
    person = faker.name()

    # Printed blocks 
    behoerde = f"Stadtverwaltung {stadt}\nAmt für öffentliche Ordnung"
    adressat_block = f"{person}\n{faker.street_address()}\n{faker.postcode()} {faker.city()}"

    aktenzeichen = f"AZ-{random.randint(100000, 999999)}"
    betrag = round(random.uniform(15.0, 80.0), 2)
    grund = random.choice(["Falschparken", "Verlust Personalausweis", "Meldebescheinigung", "Hundesteuer"])
    datum = faker.date_this_year().strftime("%d.%m.%Y")
    frist = (faker.date_this_year() + timedelta(days=14)).strftime("%d.%m.%Y")

    data = {
        "typ": "bescheid",
        "behoerde": behoerde,
        "adressat": adressat_block,
        "aktenzeichen": aktenzeichen,
        "datum": datum,
        "grund": grund,
        "betrag": betrag,
        "zahlungsfrist": frist,
    }

    draw.text(
        (50, 50),
        f"Stadtverwaltung {stadt}\nAmt für öffentliche Ordnung\n{faker.postcode()} {stadt}",
        fill="black",
        font=get_font(14),
    )
    draw.text((550, 50), f"Datum: {datum}\nAZ: {aktenzeichen}", fill="black", font=font_reg)
    draw.text((50, 180), f"Herrn/Frau\n{adressat_block}", fill="black", font=font_reg)

    y = 350
    draw.text((50, y), f"GEBÜHRENBESCHEID: {grund.upper()}", fill="black", font=font_bold)

    y += 60
    text_lines = [
        f"Sehr geehrte(r) {person.split()[-1]},",
        "",
        f"für die Amtshandlung '{grund}' wird gemäß der Gebührenordnung",
        f"der Stadt {stadt} eine Verwaltungsgebühr festgesetzt.",
        "",
        f"Festgesetzter Betrag:   {betrag:.2f} Euro",
        "",
        f"Bitte überweisen Sie den Betrag bis spätestens {frist} auf das",
        "unten angegebene Konto unter Angabe des Aktenzeichens.",
        "",
        "Rechtsbehelfsbelehrung:",
        "Gegen diesen Bescheid kann innerhalb eines Monats Widerspruch eingelegt werden.",
    ]

    for line in text_lines:
        font_use = font_bold if "Betrag:" in line else font_reg
        draw.text((50, y), line, fill="black", font=font_use)
        y += 25

    save_as_png_and_json(img, data, docs_dir, gt_dir, "bescheid", "NOT", index)


def generate_reisekosten(index: int, docs_dir: Path, gt_dir: Path):
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_reg = get_font(16)

    name = faker.name()
    dest = faker.city()
    date_start = faker.date_this_month()
    date_end = date_start + timedelta(days=2)

    transport = round(random.uniform(20, 150), 2)
    hotel = round(random.uniform(80, 300), 2)
    tagegeld = round(28.00 * 3, 2)
    total = round(transport + hotel + tagegeld, 2)

    data = {
        "typ": "reisekosten",
        "mitarbeiter": name,
        "zielort": dest,
        "start": date_start.strftime("%d.%m.%Y"),
        "ende": date_end.strftime("%d.%m.%Y"),
        "kosten_details": {
            "transport": transport,
            "hotel": hotel,
            "tagegeld": tagegeld,
        },
        "erstattungsbetrag": total,
    }

    draw_header(draw, "REISEKOSTENABRECHNUNG", width)

    y = 120
    draw.text((50, y), f"Mitarbeiter: {name}", fill="black", font=font_reg)
    y += 30
    draw.text((50, y), f"Reiseziel: {dest}", fill="black", font=font_reg)
    y += 30
    draw.text((50, y), f"Zeitraum: {data['start']} bis {data['ende']}", fill="black", font=font_reg)

    y += 60
    draw.rectangle((50, y, 750, y + 30), fill="lightgrey")
    draw.text((60, y + 5), "Kostenart", fill="black", font=get_font(16, True))
    draw.text((600, y + 5), "Betrag (EUR)", fill="black", font=get_font(16, True))
    y += 40

    items = [
        ("Fahrtkosten", transport),
        ("Übernachtungskosten", hotel),
        ("Verpflegungsmehraufwand", tagegeld),
    ]

    for label, amount in items:
        draw.text((60, y), label, fill="black", font=font_reg)
        draw.text((600, y), f"{amount:.2f}", fill="black", font=font_reg)
        draw.line((50, y + 25, 750, y + 25), fill="gray", width=1)
        y += 40

    y += 20
    draw.text((450, y), "Erstattungsbetrag:", fill="black", font=get_font(18, True))
    draw.text((600, y), f"{total:.2f}", fill="black", font=get_font(18, True))

    save_as_png_and_json(img, data, docs_dir, gt_dir, "reisekosten", "EXP", index)


def generate_meldebescheinigung(index: int, docs_dir: Path, gt_dir: Path):
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_reg = get_font(16)
    font_bold = get_font(16, bold=True)
    font_small = get_font(12)

    stadt = faker.city()
    name = faker.name()
    geb_datum = faker.date_of_birth(minimum_age=18, maximum_age=90).strftime("%d.%m.%Y")
    einzug = faker.date_between(start_date="-5y", end_date="today").strftime("%d.%m.%Y")
    ausstellungsdatum = datetime.now().strftime("%d.%m.%Y")

    current_address = f"{faker.street_address()}, {faker.postcode()} {stadt}"
    old_address = f"{faker.street_address()}, {faker.postcode()} {faker.city()}"

    data = {
        "typ": "meldebescheinigung",
        "behoerde": f"Einwohnermeldeamt {stadt}",
        "person": {
            "name": name,
            "geburtsdatum": geb_datum,
        },
        "wohnungen": {
            "aktuell": current_address,
            "einzugsdatum": einzug,
            "vorherig": old_address,
        },
        "ausstellungsdatum": ausstellungsdatum,
    }

    draw.text((50, 40), f"Stadt {stadt}", fill="black", font=font_bold)
    draw.text((50, 70), "Einwohnermeldeamt / Bürgerbüro", fill="black", font=font_reg)
    draw.line((50, 100, 750, 100), fill="black", width=2)

    draw.text((50, 150), "AMTLICHE MELDEBESCHEINIGUNG", fill="black", font=get_font(24, bold=True))
    draw.text((50, 190), "nach § 18 Bundesmeldegesetz (BMG)", fill="black", font=font_small)

    y = 250
    draw.text(
        (50, y),
        "Zu der folgenden Person sind im Melderegister folgende Daten gespeichert:",
        fill="black",
        font=font_reg,
    )
    y += 50

    fields = [
        ("Familienname, Vornamen:", name),
        ("Geburtsdatum:", geb_datum),
        ("", ""),
        ("Gegenwärtige Anschrift:", current_address),
        ("Einzugsdatum:", einzug),
        ("", ""),
        ("Vorherige Anschrift:", old_address),
    ]

    for label, val in fields:
        if label:
            draw.text((50, y), label, fill="black", font=font_bold)
            draw.text((350, y), val, fill="black", font=font_reg)
        y += 40

    y += 80
    draw.text((50, y), f"{stadt}, den {ausstellungsdatum}", fill="black", font=font_reg)

    draw.ellipse((400, y - 20, 500, y + 80), outline="blue", width=3)
    draw.text((420, y + 20), "SIEGEL", fill="blue", font=font_small)
    draw.text(
        (50, y + 60),
        "Dieses Schreiben wurde maschinell erstellt und ist ohne Unterschrift gültig.",
        fill="gray",
        font=font_small,
    )

    save_as_png_and_json(img, data, docs_dir, gt_dir, "meldebescheinigung", "MEL", index)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic German admin documents + GT (PNG).")
    parser.add_argument(
        "--dataset",
        default="generated_de_v1",
        help="Dataset folder name under tests/datasets/ (default: generated_de_v1)",
    )
    parser.add_argument(
        "--num-per-type",
        type=int,
        default=15,
        help="Number of documents to generate per type (default: 15)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional)",
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    dataset_root = REPO_ROOT / "tests" / "datasets" / args.dataset
    docs_dir, gt_dir = ensure_dataset_folders(dataset_root)

    print(f"Generating dataset: {dataset_root}")
    print(f"Docs: {docs_dir}")
    print(f"GT:   {gt_dir}")
    print(f"Target: {args.num_per_type} documents per type")
    print("Applying realistic scan effects (skew, noise, blur)...")

    for i in range(1, args.num_per_type + 1):
        generate_urlaubsantrag(i, docs_dir, gt_dir)
        generate_rechnung(i, docs_dir, gt_dir)
        generate_reisekosten(i, docs_dir, gt_dir)
        generate_bescheid(i, docs_dir, gt_dir)
        generate_meldebescheinigung(i, docs_dir, gt_dir)

    manifest = {
        "dataset": args.dataset,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "num_per_type": args.num_per_type,
        "types": ["urlaubsantrag", "rechnung", "reisekosten", "bescheid", "meldebescheinigung"],
        "notes": "Synthetic PNG documents + JSON ground truth. Images include scan artifacts (noise/blur/skew).",
        "seed": args.seed,
    }

    with (dataset_root / "dataset_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\nGeneration complete.")


if __name__ == "__main__":
    main()
