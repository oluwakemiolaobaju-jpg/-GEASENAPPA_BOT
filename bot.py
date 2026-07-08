import os
import logging
import requests
from io import BytesIO
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
REMOVE_BG_API_KEY = os.environ["REMOVE_BG_API_KEY"]
REMOVE_BG_URL = "https://api.remove.bg/v1.0/removebg"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a photo and I'll remove its background for you!\n\n"
        "Just send any image and I'll return it as a PNG with a transparent background."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me any photo (as a picture or a file) and I'll remove the background automatically."
    )


async def remove_background(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
    processing_msg = await update.message.reply_text("🔄 Removing background, please wait...")

    try:
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
        elif update.message.document and update.message.document.mime_type.startswith("image/"):
            file = await update.message.document.get_file()
        else:
            await processing_msg.edit_text("Please send a valid image.")
            return

        photo_bytes = await file.download_as_bytearray()

        response = requests.post(
            REMOVE_BG_URL,
            files={"image_file": bytes(photo_bytes)},
            data={"size": "auto"},
            headers={"X-Api-Key": REMOVE_BG_API_KEY},
            timeout=60,
        )

        if response.status_code == 200:
            result_image = BytesIO(response.content)
            result_image.name = "no_bg.png"
            await context.bot.send_document(
                chat_id=chat_id,
                document=result_image,
                filename="no_bg.png",
                caption="✅ Here's your image with the background removed!",
            )
            await processing_msg.delete()
        else:
            try:
                error_detail = response.json().get("errors", [{}])[0].get("title", "Unknown error")
            except Exception:
                error_detail = response.text
            logger.error(f"remove.bg error: {response.status_code} - {response.text}")
            await processing_msg.edit_text(f"❌ Something went wrong: {error_detail}")

    except Exception as e:
        logger.exception("Error processing image")
        await processing_msg.edit_text(f"❌ An error occurred: {str(e)}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send me a photo, not text 🙂")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, remove_background))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
