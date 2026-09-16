"""Telegram bot untuk mengubah beberapa gambar menjadi satu PDF yang dapat dikustom."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from PIL import Image, ImageColor, ImageOps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)

MAX_IMAGES = 30
MAX_FILE_BYTES = 20 * 1024 * 1024
MM_PER_INCH = 25.4
PRESETS_MM = {"a4": (210, 297), "a3": (297, 420), "a5": (148, 210), "letter": (215.9, 279.4), "legal": (215.9, 355.6)}
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class PdfSettings:
    filename: str = "gambar.pdf"
    page_size: tuple[float, float] = PRESETS_MM["a4"]
    page_label: str = "A4"
    orientation: Literal["auto", "portrait", "landscape"] = "auto"
    margin_mm: float = 10
    fit: Literal["contain", "cover", "stretch"] = "contain"
    background: str = "#FFFFFF"


@dataclass
class Session:
    files: list[tuple[str, bytes]] = field(default_factory=list)
    settings: PdfSettings = field(default_factory=PdfSettings)


def session(context: ContextTypes.DEFAULT_TYPE) -> Session:
    value = context.user_data.get("pdf_session")
    if value is None:
        value = Session()
        context.user_data["pdf_session"] = value
    return value


def clean_filename(value: str) -> str:
    value = Path(value.strip()).name
    value = re.sub(r"[^\w .()-]", "_", value, flags=re.UNICODE).strip(" .")
    if not value:
        raise ValueError("Nama file tidak boleh kosong.")
    return value[:100] + ("" if value.lower().endswith(".pdf") else ".pdf")


def parse_size(value: str) -> tuple[float, float, str]:
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|in)?\s*", value, re.I)
    if not match:
        raise ValueError("Gunakan format `lebar x tinggi mm`, misalnya `300x300 mm`.")
    width, height = (float(item.replace(",", ".")) for item in match.group(1, 2))
    unit = (match.group(3) or "mm").lower()
    multiplier = {"mm": 1, "cm": 10, "in": MM_PER_INCH}[unit]
    width, height = width * multiplier, height * multiplier
    if not (20 <= width <= 2000 and 20 <= height <= 2000):
        raise ValueError("Ukuran harus berada di antara 20 dan 2000 mm.")
    return width, height, f"{width:g} × {height:g} mm"


def options_text(state: Session) -> str:
    s = state.settings
    return (
        "<b>Pengaturan PDF</b>\n"
        f"• Nama: <code>{s.filename}</code>\n"
        f"• Halaman: {s.page_label} ({s.page_size[0]:g} × {s.page_size[1]:g} mm)\n"
        f"• Orientasi: {s.orientation}\n"
        f"• Margin: {s.margin_mm:g} mm\n"
        f"• Tata letak gambar: {s.fit}\n"
        f"• Latar: {s.background}\n"
        f"• Antrean gambar: {len(state.files)}/{MAX_IMAGES}"
    )


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("A4", callback_data="size:a4"), InlineKeyboardButton("A5", callback_data="size:a5"), InlineKeyboardButton("Letter", callback_data="size:letter")],
            [InlineKeyboardButton("Potret", callback_data="orientation:portrait"), InlineKeyboardButton("Lanskap", callback_data="orientation:landscape"), InlineKeyboardButton("Otomatis", callback_data="orientation:auto")],
            [InlineKeyboardButton("Pas / tanpa potong", callback_data="fit:contain"), InlineKeyboardButton("Penuhi / potong", callback_data="fit:cover"), InlineKeyboardButton("Regangkan", callback_data="fit:stretch")],
            [InlineKeyboardButton("♻ Reset pengaturan", callback_data="reset"), InlineKeyboardButton("🗑 Kosongkan gambar", callback_data="clear")],
        ]
    )


def render_page(raw: bytes, settings: PdfSettings) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        width_mm, height_mm = settings.page_size
        if settings.orientation == "auto":
            if source.width > source.height:
                width_mm, height_mm = max(width_mm, height_mm), min(width_mm, height_mm)
            else:
                width_mm, height_mm = min(width_mm, height_mm), max(width_mm, height_mm)
        elif settings.orientation == "landscape":
            width_mm, height_mm = max(width_mm, height_mm), min(width_mm, height_mm)
        else:
            width_mm, height_mm = min(width_mm, height_mm), max(width_mm, height_mm)

        # 150 DPI gives a compact Telegram-friendly PDF while retaining legible text.
        dpi = 150
        page_size = (round(width_mm / MM_PER_INCH * dpi), round(height_mm / MM_PER_INCH * dpi))
        margin = round(settings.margin_mm / MM_PER_INCH * dpi)
        available = (max(1, page_size[0] - margin * 2), max(1, page_size[1] - margin * 2))
        if settings.fit == "stretch":
            resized = source.resize(available, Image.Resampling.LANCZOS)
        else:
            scale = (max if settings.fit == "cover" else min)(available[0] / source.width, available[1] / source.height)
            resized = source.resize((max(1, round(source.width * scale)), max(1, round(source.height * scale))), Image.Resampling.LANCZOS)
        page = Image.new("RGB", page_size, ImageColor.getrgb(settings.background))
        page.paste(resized, ((page_size[0] - resized.width) // 2, (page_size[1] - resized.height) // 2))
        return page


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Halo! Kirim foto atau dokumen JPG/PNG/WEBP, lalu gunakan /buatpdf.\n\n"
        "Atur nama dan ukuran lewat /nama, /ukuran, /margin, /fit, /orientasi, atau tombol /pengaturan.\n"
        "Gunakan /bantuan untuk contoh lengkap."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>Cara pakai</b>\n"
        "1. Kirim hingga 30 gambar (foto dapat dikirim sekaligus).\n"
        "2. Atur bila perlu, misalnya: <code>/nama laporan September</code>\n"
        "3. Jalankan <code>/buatpdf</code>; semua gambar digabung menjadi satu PDF.\n\n"
        "<b>Perintah kustom</b>\n"
        "• /pengaturan — lihat tombol pilihan cepat\n"
        "• /nama nama-file.pdf\n"
        "• /ukuran A4 | A3 | A5 | Letter | 300x300 mm\n"
        "• /margin 0 sampai 100 (mm)\n"
        "• /orientasi otomatis | potret | lanskap\n"
        "• /fit pas | penuhi | regangkan\n"
        "• /latar #FFFFFF (warna halaman)\n"
        "• /hapus — hapus semua gambar dari antrean\n\n"
        "Batas: 30 gambar, maksimal 20 MB per berkas."
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = session(context)
    await update.message.reply_text(options_text(state), parse_mode="HTML", reply_markup=keyboard())


async def name_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    value = " ".join(context.args)
    try:
        session(context).settings.filename = clean_filename(value)
    except ValueError as error:
        await update.message.reply_text(f"{error}\nContoh: <code>/nama invoice-september.pdf</code>", parse_mode="HTML")
        return
    await update.message.reply_text(f"Nama PDF: <code>{session(context).settings.filename}</code>", parse_mode="HTML")


async def size_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    value = " ".join(context.args).lower()
    state = session(context)
    if value in PRESETS_MM:
        state.settings.page_size, state.settings.page_label = PRESETS_MM[value], value.upper()
    else:
        try:
            width, height, label = parse_size(value)
        except ValueError as error:
            await update.message.reply_text(f"{error}\nContoh: <code>/ukuran 300x300 mm</code>", parse_mode="HTML")
            return
        state.settings.page_size, state.settings.page_label = (width, height), label
    await update.message.reply_text(f"Ukuran halaman diatur ke {state.settings.page_label}.")


async def margin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        value = float(" ".join(context.args).replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Margin harus berupa angka 0–100 mm. Contoh: <code>/margin 8</code>", parse_mode="HTML")
        return
    session(context).settings.margin_mm = value
    await update.message.reply_text(f"Margin diatur menjadi {value:g} mm.")


async def choice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command, value = update.message.text.split(maxsplit=1) if context.args else (update.message.text, "")
    value = value.lower().strip()
    s = session(context).settings
    mappings = {
        "/orientasi": ({"otomatis": "auto", "auto": "auto", "potret": "portrait", "portrait": "portrait", "lanskap": "landscape", "landscape": "landscape"}, "orientation"),
        "/fit": ({"pas": "contain", "contain": "contain", "penuhi": "cover", "cover": "cover", "regangkan": "stretch", "stretch": "stretch"}, "fit"),
    }
    allowed, attr = mappings[command]
    if value not in allowed:
        await update.message.reply_text(f"Pilihan tidak dikenal. Gunakan salah satu: {', '.join(allowed)}.")
        return
    setattr(s, attr, allowed[value])
    await update.message.reply_text(f"{command[1:].capitalize()} diatur ke {allowed[value]}.")


async def background_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    value = "".join(context.args).upper()
    try:
        ImageColor.getrgb(value)
    except ValueError:
        await update.message.reply_text("Gunakan warna hex, misalnya <code>/latar #FFF8E1</code>.", parse_mode="HTML")
        return
    session(context).settings.background = value
    await update.message.reply_text(f"Warna latar diatur ke {value}.")


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    document = message.document
    if document and (document.mime_type not in IMAGE_MIMES or document.file_size > MAX_FILE_BYTES):
        await message.reply_text("Dokumen harus JPG, PNG, atau WEBP dan maksimal 20 MB.")
        return
    state = session(context)
    if len(state.files) >= MAX_IMAGES:
        await message.reply_text(f"Antrean sudah penuh (maksimal {MAX_IMAGES} gambar). Gunakan /buatpdf atau /hapus.")
        return
    telegram_file = await (message.photo[-1] if message.photo else document).get_file()
    raw = bytes(await telegram_file.download_as_bytearray())
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
    except (OSError, SyntaxError):
        await message.reply_text("Berkas gambar tidak dapat dibaca.")
        return
    state.files.append((document.file_name if document else f"foto-{len(state.files) + 1}.jpg", raw))
    await message.reply_text(f"✓ Gambar ditambahkan ({len(state.files)}/{MAX_IMAGES}). Kirim lagi atau gunakan /buatpdf.")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session(context).files.clear()
    await update.message.reply_text("Antrean gambar telah dikosongkan. Pengaturan PDF tetap disimpan.")


async def create_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = session(context)
    if not state.files:
        await update.message.reply_text("Belum ada gambar. Kirim foto terlebih dahulu.")
        return
    await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
    await update.message.reply_text(f"Membuat PDF dari {len(state.files)} gambar…")
    try:
        pages = await asyncio.to_thread(lambda: [render_page(raw, state.settings) for _, raw in state.files])
        output = io.BytesIO()
        await asyncio.to_thread(lambda: pages[0].save(output, "PDF", save_all=True, append_images=pages[1:], resolution=150.0))
        output.seek(0)
        output.name = state.settings.filename
        await update.message.reply_document(document=output, filename=state.settings.filename, caption=f"PDF selesai: {len(pages)} halaman.")
        state.files.clear()
    except Exception:
        LOGGER.exception("PDF creation failed")
        await update.message.reply_text("PDF gagal dibuat. Pastikan gambar valid lalu coba lagi.")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    state = session(context)
    action, _, value = query.data.partition(":")
    if action == "size":
        state.settings.page_size, state.settings.page_label = PRESETS_MM[value], value.upper()
    elif action in {"orientation", "fit"}:
        setattr(state.settings, action, value)
    elif action == "reset":
        state.settings = PdfSettings()
    elif action == "clear":
        state.files.clear()
    await query.edit_message_text(options_text(state), parse_mode="HTML", reply_markup=keyboard())


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN sebelum menjalankan bot.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["help", "bantuan"], help_command))
    app.add_handler(CommandHandler("pengaturan", settings_command))
    app.add_handler(CommandHandler("nama", name_command))
    app.add_handler(CommandHandler("ukuran", size_command))
    app.add_handler(CommandHandler("margin", margin_command))
    app.add_handler(CommandHandler(["orientasi", "fit"], choice_command))
    app.add_handler(CommandHandler("latar", background_command))
    app.add_handler(CommandHandler("hapus", clear_command))
    app.add_handler(CommandHandler("buatpdf", create_pdf))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
