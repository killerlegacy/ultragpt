import os
import time
import logging
import openai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, Updater, ContextTypes,ConversationHandler, CommandHandler, MessageHandler, filters, CallbackContext
from datetime import datetime, timedelta
import sqlite3
import ffmpeg


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

openai.api_key = "Your Api key"

# Set up database connection
conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        is_paid INTEGER,
        trial_start_time TEXT
    )
''')
conn.commit()

# Helper functions to check if a user is a free user or a paid user
def is_free_user(user_id):
    c.execute('SELECT * FROM users WHERE user_id=? AND is_paid=0', (user_id,))
    return c.fetchone() is not None

def is_paid_user(user_id):
    c.execute('SELECT * FROM users WHERE user_id=? AND is_paid=1', (user_id,))
    return c.fetchone() is not None

# Helper function to check if a free user's trial has expired
def has_trial_expired(user_id):
    c.execute('SELECT trial_start_time FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    if row is None:
        return False
    trial_start_time = datetime.fromisoformat(row[0])
    trial_duration = timedelta(hours=3)
    return datetime.now() - trial_start_time > trial_duration

# Handle text messages from users
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    print(user_id)
    # Check if the user has sent the custom message to become a paid user
    if update.message.text == 'to get paid contact admin':
        # TODO: Send a message to the admin with instructions on how to make this user a paid user
        await update.message.reply_text('Thank you! The admin has been notified and will contact you shortly.')
        return

    # Check if the user is allowed to use the chatbot
    if is_paid_user(user_id) or (is_free_user(user_id) and not has_trial_expired(user_id)):
        # Generate a response using the OpenAI API
        prompt = update.message.text
        response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0301",
        messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
        await update.message.reply_text(response_text)
    else:
        # If the user is not allowed to use the chatbot, check if they are a new user
        c.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
        if c.fetchone() is None:
            # If the user is a new user, start their free trial
            c.execute('INSERT INTO users (user_id, is_paid, trial_start_time) VALUES (?, 0, ?)', (user_id, datetime.now().isoformat()))
            conn.commit()
            await update.message.reply_text('Welcome! You have been given a free 3-hour trial. To continue using this chatbot after your trial expires, Contact the admin.')
        else:
            # If the user's trial has expired, ask them to become a paid user
            await update.message.reply_text('Your trial has expired. To continue using this chatbot, please become a paid user by contacting the admin.')

# Handle /start command from users (i.e., when a user starts a chat with the bot)
async def start(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:

    await update.message.reply_text(
        'This chatbot generate human-like responses to user messages. Free users can use GptUltra+ for 3 hours before their trial expires contact the admin. This chatbot is a powerful tool that can provide users with intelligent and engaging conversation.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("This chatbot is a powerful tool that can provide users with intelligent and engaging conversation.\n You can use following commands.\n 1. /help\n 2. /start\n 3. /add_users\n 4. /Contact_admin ")

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /contact_admin is issued."""
    await update.message.reply_text("Dm here to get paid subscription @Alishah964 ")
# Handle /add_users command from the owner of the chatbot

OWNER_USER_ID = 1075995888

async def add_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != OWNER_USER_ID:
        await update.message.reply_text('Sorry, only the owner of this chatbot can use this command.')
        return
    user_id = context.args[0]
    try:
        user_id = int(user_id)
    except ValueError:
        await update.message.reply_text('Invalid user ID.')
        return
    c.execute('INSERT OR IGNORE INTO users (user_id, is_paid) VALUES (?, 1)', (user_id,))
    conn.commit()
    cursor = conn.execute("SELECT user_id, is_paid from users")
    for row in cursor:
        print ("USER ID = ", row[0])
        print ("PAID = ", row[1], "\n")

    print ("Operation done successfully")
    await update.message.reply_text(f'User {user_id} has been added successfully to the database.')

#Use to remove user
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != OWNER_USER_ID:
        await update.message.reply_text("Sorry, only the owner of this chatbot use this command.")
        return
    user_id = context.args[0]
    try:
        user_id = int(user_id)
    except ValueError:
        await update.message.reply_text("Invalid User ID.")
        return
    conn.execute(f"DELETE from users where user_id = {user_id}")
    conn.commit()
    cursor = conn.execute("SELECT user_id, is_paid from users")
    for row in cursor:
        print ("USER ID = ", row[0])
        print ("PAID = ", row[1], "\n")

    print ("Operation done successfully")
    await update.message.reply_text(f'User {user_id} has been removed successfully from the database.')

#Use to transcribe audio file
async def audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    print(user_id)
    if is_paid_user(user_id) or (is_free_user(user_id) and not has_trial_expired(user_id)):

    #fetch audio file from user
        file_id = update.message.audio.file_id
        file_path = f"{file_id}.mp3"
        audio_file = await context.bot.get_file(file_id)
        await audio_file.download_to_drive(file_path)
        audio_file_cv= open(file_path, "rb")
        transcript = openai.Audio.transcribe(
            model = "whisper-1",
            file = audio_file_cv,
            response_format = 'text',
            Temperature = 0.2)
        await update.message.reply_text(transcript)
        print(f"download successful:{file_path}")
        audio_file_cv.close()
        time.sleep(5)
        os.remove(file_path)
    else:
        # If the user's trial has expired, ask them to become a paid user
        await update.message.reply_text('Your trial has expired. To continue using this chatbot, please become a paid user by contacting the admin.')

#Use to transcribe Voice message
async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    print(user_id)
    if is_paid_user(user_id) or (is_free_user(user_id) and not has_trial_expired(user_id)):
    #fetch audio file from user
        file_id = update.message.voice.file_id
        file_path = file_id
        audio_file = await context.bot.get_file(file_id)
        await audio_file.download_to_drive(file_path)
    
    # Load the OGG audio file
        input_file = ffmpeg.input(file_path)
        mp3_file_path = f"{file_id}.mp3"
    # Output MP3 file
        output_file = ffmpeg.output(input_file, mp3_file_path, codec='libmp3lame', bitrate='128k')

    # Run ffmpeg command to convert OGG to MP3
        ffmpeg.run(output_file)
        print("Conversion to MP3 complete")
#to use ffmpeg we should downloadffmpeg.exe and place it in python installation folder
        audio_file_cv= open(mp3_file_path, "rb")
        transcript = openai.Audio.transcribe(
            model = "whisper-1",
            file = audio_file_cv,
            response_format = 'text',
            Temperature = 0.2)
        await update.message.reply_text(transcript)
        print(f"download successful:{file_path}")
        audio_file_cv.close()
        time.sleep(5)
        os.remove(mp3_file_path)
        os.remove(file_path)
    else:
        # If the user's trial has expired, ask them to become a paid user
        await update.message.reply_text('Your trial has expired. To continue using this chatbot, please become a paid user by contacting the admin \n use command /contact_admin \n For help type /help.')
   
def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("Your bot token").build()
# Add handlers to the dispatcher
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.AUDIO & ~filters.COMMAND, audio_message))
    application.add_handler(MessageHandler(filters.VOICE & ~filters.COMMAND, voice_message))
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('add_users', add_users))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("Contact_admin",contact_command))
    application.add_handler(CommandHandler ("remove",remove))
    application.run_polling()

if __name__ == "__main__":
    main()
# Close the database connection
conn.close()
