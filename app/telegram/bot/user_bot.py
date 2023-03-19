import logging
import json
import pyqrcode
import requests
import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, LabeledPrice, InlineKeyboardButton,
    InlineKeyboardMarkup, PhotoSize
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    ConversationHandler, MessageHandler, StringCommandHandler,
    filters, PreCheckoutQueryHandler, CallbackQueryHandler, CallbackContext,
)
import os
from dotenv import load_dotenv
from sys import platform
from PIL import Image

load_dotenv()


TELE_TOKEN_TEST = os.getenv("TELE_TOKEN_TEST")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
endpoint_url = os.getenv("BACKEND_ENDPOINT", "http://localhost:3000")
webhook_url = os.getenv("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 5000))

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



ROUTE, NEW_USER, NEW_USER_NAME, SHOW_QR = range(4)

"""
=============================================================================================
start: Send bot description and provide user with wallet & event options, 
cancel: Exit current action
unknown: User sends an unknown commad/message/invalid response
error_handler: Error occured during execution and user is informed
=============================================================================================
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Wallet", callback_data="wallet_options"),],
        [InlineKeyboardButton("Event", callback_data="event_options"),]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = ("*Welcome to Mynt ticketing bot!*\n\n"
               "This bot allows you to create a Mynt wallet so that you can easily purchase tickets for upcoming events.\n\n"
               "To get started, please create a Mynt wallet by selecting Top Up Wallet.\n"
               "Once you have sufficient balance in your Mynt wallet, you can purchase a ticket for an event by selecting Register for an Event.\n\n"
               "You can access other *wallet* & *event* functionalities by clicking on the respective buttons below.")

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message, 
            parse_mode="markdown", 
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=message, 
            parse_mode="markdown", 
            reply_markup=reply_markup
        )

    return ROUTE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Thank you for visiting the Mynt Ticketing Bot"
    )
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_default_message(
        update, 
        context, 
        "Sorry, I didn't understand that command. \n"
        "Use /start to head back to the main menu"
    )
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # await context.bot.send_message(
    #     chat_id=update.effective_chat.id,
    #     text="Sorry, an unexpected error occurred \n"
    #     "Please try again later")
    return ConversationHandler.END

""""
=============================================================================================
wallet_options: Modify the current text (start msg) and display wallet options
event_options: Modify the current text (start msg) and display event options
send_default_message: Send message displaying the text(variable) passed, as well as Menu option
update_default_message: Update the previous message with the text(variable) passed, as well as Menu Option
=============================================================================================
"""

async def wallet_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("View Wallet Balance",callback_data="view_wallet_balance"),],
        [InlineKeyboardButton("View Transaction History",callback_data="view_transaction_history_1"),],
        [InlineKeyboardButton("Top Up Wallet", callback_data="top_up_wallet"),],
        [InlineKeyboardButton("< Back", callback_data="start"),],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="Please select one of the following options below", reply_markup=reply_markup
    )
    return ROUTE


async def event_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("View Ongoing Events", callback_data="view_events"),],
        [InlineKeyboardButton("View Registration Status", callback_data="check_registration"),],
        [InlineKeyboardButton("Redeem Event Ticket", callback_data="redeem"),],
        [InlineKeyboardButton("< Back", callback_data="start"),],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="Please select one of the following options below", reply_markup=reply_markup
    )
    return ROUTE


async def send_default_message(update, context: ContextTypes.DEFAULT_TYPE, text):
    keyboard = [[InlineKeyboardButton("< Back to Menu", callback_data="start"),],]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup, 
    )
    
    
async def update_default_message(update, context: ContextTypes.DEFAULT_TYPE, text):
    keyboard = [[InlineKeyboardButton("< Back to Menu", callback_data="start"),],]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )

""""
=============================================================================================
get_user_id_from_query: Reusable function for retrieving user id after a user has clicked a button
view_wallet_balance: Display balance of user's wallet
view_transaction_history: Display transaction history of user
=============================================================================================
"""
async def get_user_id_from_query(update):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    return user_id

async def view_wallet_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await get_user_id_from_query(update)
    logger.info(f"Retrieving wallet balance for User: {user_id}")
    response = requests.get(endpoint_url + f"/viewWalletBalance/{user_id}")
    response_data = response.json()
    user_balance = response_data['balance']

    text=f'Your wallet balance is ${user_balance}'
    await update_default_message(update, context, text)
    return ROUTE

def format_txn_history(response_data):
    if len(response_data) > 0:
        text = "Your transaction History is as follows \n\n"

        for transaction in response_data:
            transaction_type = transaction['transactionType']
            amount = transaction['amount']
            time = transaction['timestamp']
            event = transaction['eventTitle'] if 'eventTitle' in transaction else "-"

            text += f"Transaction Type: *{transaction_type}*\n" \
                f"Amount: ${amount}\n" \
                f"Time: {time}\n" \
                f"Event: {event}\n\n"
    else:
        text = "You have no prior transactions"
    return text
    
async def view_transaction_history(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    logger.info(f"Retrieving transaction history for User: {user_id}")
    response = requests.get(endpoint_url + f"/viewTransactionHistory/{user_id}")
    response_data = response.json()

    # Reverse the order of the response_data list to show latest transactions first
    response_data.reverse()

    # Get the current page number from user_data, default to page 1
    page_num = int(query.data.split("_")[-1])
    context.user_data['page_num'] = page_num

    # Calculate the starting and ending index of transactions to display
    num_per_page = 3
    start_idx = (page_num - 1) * num_per_page
    end_idx = start_idx + num_per_page

    # Slice the transactions to display only the ones for the current page
    transactions = response_data[start_idx:end_idx]

    # Format the transactions as text
    text = format_txn_history(transactions)

    # Create the inline keyboard for pagination
    keyboard = [[InlineKeyboardButton("< Back to Menu", callback_data="start"),],]
    if start_idx > 0:
        # Add "Previous" button if not on the first page
        keyboard.append([InlineKeyboardButton("Previous", callback_data=f"view_transaction_history_{page_num-1}")])
    if end_idx < len(response_data):
        # Add "Next" button if not on the last page
        keyboard.append([InlineKeyboardButton("Next", callback_data=f"view_transaction_history_{page_num+1}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the message with pagination and update user_data with the current page number
    await query.edit_message_text(text=text, reply_markup=reply_markup)

    return ROUTE

""""
=============================================================================================
redeem: Displays events that the user has successfully registered for and are yet to be redeemed. 
    After user picks an event, show_QR will be called that will display a QR code containing information 
    on the user's id, event status and event title
check_authorisation (merchant): should be in the merchant side. we get the telegram id, 
    use getRegistrations Firebase to see what the user has registered for, compare to the current event 
    and send a message back to the user and authoriser saying {handle} has been verified for XX event
=============================================================================================
"""

def get_successful_registrations(response_data):
    registered_events = {}
    reply_string = ''
    count = 1

    for events in response_data:
        eventTitle = events['eventTitle']
        status = events['status']
        user_id = events['userId']
        if "SUCCESSFUL" in status: 
            registered_events[eventTitle] = {
                'userId': user_id, 'status': status, 'eventTitle': eventTitle}
            reply_string += f'\n {count}. {eventTitle}'
            count += 1
            
    return registered_events, reply_string
    
    
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await get_user_id_from_query(update)
    logger.info(f"Retrieving registrations for User: {user_id}")
    response = requests.get(endpoint_url + f"/getRegistrations/{user_id}")
    response_data = response.json()

    if len(response_data) <= 0:
        await send_default_message(update, context, f"You have no registered events")
        return ROUTE

    else:
        registered_events, reply_string = get_successful_registrations(response_data)
        if len(registered_events) == 0: # if raffle was not successful - he did not get the ticket
            await send_default_message(update, context, f"You have no successful registrations")
            return ROUTE
        
        else:
            reply_string += '\n\n Which one would you like to redeem?'
            reply_keyboard = [list(registered_events.keys())]
            # very important to key the information
            context.user_data['registered_events'] = registered_events

            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="You have available tickets! You currently have: \n"
                f'{reply_string}',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True,
                ),)
            return SHOW_QR


async def show_QR(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket = update.message.text
    username = update.message.from_user.username
    user_id = update.message.from_user.id
    user_chat_id = update.effective_chat.id
    registered_events = context.user_data['registered_events']
    registered_events[ticket]['chatId'] = user_chat_id
    qr_information = registered_events[ticket]
    qr_information_str = json.dumps(qr_information)

    await update.message.reply_text(
        f'Show this QR code to redeem your ticket for {ticket}. This QR code belongs to {username}'
    )
    url = pyqrcode.create(qr_information_str)
    url.png(f'./qr_codes/{user_id}.png', scale=6)
    await update.message.reply_photo(f'./qr_codes/{user_id}.png')
    # add code to delete photo as well
    # current_path = os.getcwd()
    # if platform != 'darwin':  # windows
    #     picture_path = current_path + f'\qr_codes\{user_id}.png'
    # else:  # mac or linux
    #     picture_path = current_path + f'/qr_codes/{user_id}.png'
    # # print(f'Your current path is {picture_path}')
    # os.remove(picture_path)
    await send_default_message(
        update, 
        context, 
        "Head back the the menu if your verification was successful"
    )
    return ROUTE

""""
=============================================================================================
top_up_wallet: Prompt new user for their details
is_new_user: check whether a user is a new user
register_new_user: send API request to save user records
get_topup_amount: prompt user for top up amount
proceed_payment: send payment invoice based on top up amount
precheckout: Answer the PreQecheckoutQuery
successful_payment: Confirms successful payment and sends API request to update relevant records
=============================================================================================
"""


async def top_up_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await get_user_id_from_query(update)
    context.user_data["new_user"] = await is_new_user(user_id)
    if context.user_data["new_user"] == True:
        text=("To help us process your top-up, please provide your name in the following format: 'John'. \n"
              "This information is only required for your first top-up.")
        await update_default_message(update, context, text)
        return NEW_USER_NAME

    else:
        await get_topup_amount(update, context)
        return ROUTE

async def get_new_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    context.user_data['new_user_name'] = user_name
    await update.message.reply_text("Nice! Please provide your contact number in the following format: '81818181'.")
    return NEW_USER

async def is_new_user(user_id):
    response = requests.get(endpoint_url + f"/getUserInfo/{user_id}")
    response_data = response.json()
    if response_data['name'] == "No Such User Exists":
        return True
    else:
        return False


async def register_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_number = update.message.text
    context.user_data['new_contact_number'] = contact_number
    user_id = update.message.from_user.id
    user_handle = update.message.from_user.username
    user_name = context.user_data["new_user_name"]
    user_contact = context.user_data["new_contact_number"]
    data = {
        'user_id': user_id,
        'user_handle': user_handle,
        'user_name': user_name,
        'user_contact': user_contact,
        'chat_id' : update.effective_chat.id
    }
    logger.info(f'Saving records of new user {user_id}')

    response = requests.post(endpoint_url + "/uploadUserInfo", json=data)
    if response.status_code == 200:
        await update.message.reply_text('Successfully saved your contact info')
        await get_topup_amount(update, context)
        return ROUTE
    else:
        await update.message.reply_text('An unexpected error occurred')
        return ConversationHandler.END


async def get_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("< Back to Menu", callback_data="start"),],
        [
            InlineKeyboardButton("$10", callback_data="top_up_10"),
            InlineKeyboardButton("$50", callback_data="top_up_50"),
            InlineKeyboardButton("$100", callback_data="top_up_100"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Please select an amount to top up your Mynt Wallet",
        reply_markup=reply_markup, 
    ) 


async def proceed_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()    
    
    callback_data = update.callback_query.data[7:] ## (top_up_xx) The amount starts from 7th index
    topup_amount = int(callback_data)
    context.user_data["topup_amount"] = topup_amount

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=f"Top up Wallet",
        description="Topping up your Mynt wallet",
        payload="Custom-Payload",
        provider_token=PROVIDER_TOKEN,
        currency="SGD",
        prices=[LabeledPrice("Ticket Price", topup_amount * 100)]
    )
    return ROUTE
    

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Validating invoice payload")
    query = update.pre_checkout_query
    # check the payload
    if query.invoice_payload != "Custom-Payload":
        # answer False pre_checkout_query
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirms the successful payment."""
    user_id = update.message.from_user.id
    topup_amount = context.user_data["topup_amount"]
    logger.info(f'{user_id} has successfully topped up {topup_amount}')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        'user_id': user_id,
        'amount': topup_amount,
        'transaction_type': "TOP_UP",
        'timestamp': timestamp
    }
    response = requests.post(endpoint_url + "/topUpWallet", json=data)
    if response.status_code == 200:
        text=f"You have successfully topped up ${topup_amount}!"
        await send_default_message(update, context, text)

    else:
        await update.message.reply_text('An unexpected error occurred')
        return ConversationHandler.END

""""
=============================================================================================
view_events: View ongoing events
check_registration: View status for users' registrations
get_previous_registrations: API call to retrive previous registrations
validate_registration: Validate event title and check previous registrations
verify_balance: Check whether user has sufficient balance in in-app wallet
complete_purchase: Send API request to save payment records
complete_registration: Send API request to save registration records
=============================================================================================
"""

def format_registration_data(response_data):
    text = ""
    if response_data: # User has previously registered for events
        text += "These are your current registered events!\n\n"
        for event in response_data:
            event_title = event['eventTitle']
            status = event['status']
            text += f"Event Title: *{event_title}*\n" \
                f"Registration Status: {status}\n\n" \

    else: # User has no previous registrations
        text += "You have not registered for any events!"
    return text
   
    
async def check_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await get_user_id_from_query(update)
    logger.info(f'Checking status for {user_id}')
    response = requests.get(endpoint_url + f"/getRegistrations/{user_id}")
    response_data = response.json()
    text=format_registration_data(response_data)
    await update_default_message(update, context, text)
    return ROUTE

def is_valid_url(url):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == requests.codes.ok:
            image = Image.open(response.raw)
            return image.format == 'JPEG'
        else:
            return False
    except:
        return False
    
def format_event_data(response_data, context: ContextTypes.DEFAULT_TYPE):
    
    event_array = [] # Contains message, button and photo to be sent for each event
    events_dict = {} # Contains mapping of event titles and price, to be used in validate_registration
    
    for event in response_data:
        event_title = event['title']
        event_description = event['description']
        event_time = event['time']
        event_venue = event['venue']
        event_price = event['price']
        
        text = f"Event Title: *{event_title}*\n" \
                  f"Description: {event_description}\n" \
                  f"Time: {event_time}\n" \
                  f"Venue: {event_venue}\n" \
                  f"Price: *{event_price}*\n\n"
                    
        keyboard = [[InlineKeyboardButton(text='Register for Event', callback_data=f'title_{event_title}')],]
        reply_markup = InlineKeyboardMarkup(keyboard)
        photo_url = f"https://firebasestorage.googleapis.com/v0/b/treehoppers-mynt.appspot.com/o/{event_title}{event_time}?alt=media&token=07ddd564-df85-49a5-836a-c63f0a4045d6"
        if is_valid_url(photo_url):
            photo = PhotoSize(
                file_id=photo_url,
                file_unique_id="some_random_id",
                width=400,
                height=400
            )
        else: # Use fallback URL if it fails
            logger.info('Cant find image: '+photo_url+ " resorting to fallback")
            fallback_url = "https://ipfs.io/ipfs/QmfDTSqRjx1pgD1Jk6kfSyvGu1PhPc5GEx837ojK8wfGNi"
            photo = PhotoSize(
                file_id=fallback_url,
                file_unique_id="some_random_id",
                width=400,
                height=400
            )
        event_array.append((text, reply_markup, photo))
        
        events_dict[event_title] = event_price
        
    context.user_data["events_dict"] = events_dict
    return event_array

async def view_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Retrieving Events Information")
    query = update.callback_query
    await query.answer()
    
    response = requests.get(endpoint_url + "/viewEvents")
    response_data = response.json()
    event_array = format_event_data(response_data, context)
    
    if len(event_array) == 0:
        await update_default_message(update, context, "There are currently no ongoing events to register for")
    
    else:
        for text, reply_markup, photo in event_array:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, 
                photo=photo,
                caption=text, 
                parse_mode="markdown", 
                reply_markup=reply_markup
            )
        
        text = "Please click on the register button for the event you would like to register for."
        await send_default_message(update, context, text)
        
    return ROUTE


def get_previous_registrations(user_id, event_title):
    logger.info(f'Checking previous registrations for {user_id}')
    response = requests.get(endpoint_url + f"/getRegistrations/{user_id}")
    response_data = response.json()

    # Save event titles for events that user has previously registered for
    registered_events = []
    if response_data:
        for event in response_data:
            registered_events.append(event['eventTitle'])

    # Check if user is registering for the same event
    if event_title in registered_events:
        return True
        
    return False


async def validate_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Validating registration for user")
    query = update.callback_query
    await query.answer()   
    
    callback_data = update.callback_query.data ## (title_xx) The title starts from 5th index
    event_title = callback_data[6:]
    context.user_data["event_title"] = event_title
    
    user_id = query.from_user.id
    double_registration = get_previous_registrations(user_id, event_title)
    if double_registration:
        text=("You have already registered for this event. \n"
            "You cannot register for the same event again.")
        await send_default_message(update, context, text)
    
    else:
        # Prompt user for payment confirmation
        events_dict = context.user_data["events_dict"]
        event_price = events_dict[event_title]
        context.user_data["event_price"] = event_price
        keyboard = [
            [InlineKeyboardButton("< Back", callback_data="start")],
            [InlineKeyboardButton("Yes", callback_data="verify_balance"),]
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Do you wish to make a payment of ${event_price} for the event using your Mynt Wallet?\n'
            "Reply with Yes to confirm payment",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="markdown",
        )
        
    return ROUTE


async def verify_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  

    # Verify user has sufficient balance in in-app wallet
    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    logger.info(f"Verifying balance for user {user_id}")
    response = requests.get(endpoint_url + f"/viewWalletBalance/{user_id}")
    response_data = response.json()
    user_balance = response_data['balance']
    event_price = context.user_data["event_price"]

    # User has insufficient balance
    if user_balance < event_price:
        text=(f"You have insufficient balance in your wallet \n"
            f"Your current balance is ${user_balance} but the ticket price is ${event_price} \n"
            "Please top up your Mynt wallet!")
        await update_default_message(update, context, text)
        return ROUTE

    # User has sufficient balance
    else:
        await complete_purchase(update, context)
        await complete_registration(update, context)
        return ROUTE


async def complete_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data["user_id"]
    event_price = context.user_data["event_price"]
    event_title = context.user_data["event_title"]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        'user_id': user_id,
        'amount': event_price,
        'transaction_type': "SALE",
        'timestamp': timestamp,
        'event_title': event_title,
    }
    response = requests.post(endpoint_url + "/ticketSale", json=data)
    logger.info("Saving payment records")
    if response.status_code == 200:
        await context.bot.send_message(
            text=f"Your wallet balance has been updated successfully",
            chat_id=update.effective_chat.id
        )
    else:
        await context.bot.send_message(
            text=f"Sorry, something went wrong when updating your wallet balance",
            chat_id=update.effective_chat.id
        )


async def complete_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data["user_id"]
    event_title = context.user_data["event_title"]
    registration_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f'{user_id} has successfully registered for {event_title} at {registration_time}')
    data = {
        'user_id': user_id,
        'event_title': event_title,
        'status': 'PENDING',
        'registration_time': registration_time,
    }
    response = requests.post(endpoint_url + "/insertRegistration", json=data)
    if response.status_code == 200:
        text=(f"You have successfully registered for {event_title}. \n"
        "Please note that your registration does not guarantee a ticket, as we will be "
        "conducting a raffle to randomly select the winners. \n"
        "We will notify you of the outcome via message. \n"
        "Thank you for your interest and we hope to see you at the event!")
        await send_default_message(update, context, text)
        return ROUTE
    else:
        await update.message.reply_text("Sorry, something went wrong with your registration")
        return ConversationHandler.END


if __name__ == '__main__':
    application = ApplicationBuilder().token(TELE_TOKEN_TEST).build()

    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('cancel', cancel),
        ],
        states={
            ROUTE: {
                CallbackQueryHandler(start, pattern="^start$"),
                CallbackQueryHandler(wallet_options, pattern="^wallet_options$"),
                CallbackQueryHandler(view_wallet_balance,pattern="^view_wallet_balance$"),
                CallbackQueryHandler(view_transaction_history, pattern="^view_transaction_history_(.*)$"),
                CallbackQueryHandler(top_up_wallet, pattern="^top_up_wallet$"),
                CallbackQueryHandler(proceed_payment, pattern="^top_up_10$"),
                CallbackQueryHandler(proceed_payment, pattern="^top_up_50$"),
                CallbackQueryHandler(proceed_payment, pattern="^top_up_100$"),
                CallbackQueryHandler(event_options, pattern="^event_options$"),
                CallbackQueryHandler(view_events, pattern="^view_events$"),
                CallbackQueryHandler(check_registration, pattern="^check_registration$"),
                CallbackQueryHandler(validate_registration, pattern="^title_(.*)$"), ## Can handle any callback pattern,
                CallbackQueryHandler(verify_balance, pattern="^verify_balance$"),
                CallbackQueryHandler(redeem, pattern="^redeem$"),
                CommandHandler('start', start),
                CommandHandler('cancel', cancel),
            },
            NEW_USER: [MessageHandler(filters.Regex("^[0-9]{8}$"), register_new_user)],
            NEW_USER_NAME: [MessageHandler(filters.Regex("^[a-zA-Z]+$"), get_new_user_name)],
            SHOW_QR: [MessageHandler(filters.TEXT, show_QR)],
        },
        fallbacks=[MessageHandler(filters.TEXT, unknown)]
    )
    application.add_handler(conversation_handler)

    application.add_handler(PreCheckoutQueryHandler(precheckout)) # Payment Services
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment)) # Payment Services
    application.add_handler(MessageHandler(filters.TEXT, unknown)) # Unknown messages
    application.add_error_handler(error_handler) # Error handling

    if os.getenv("WEBHOOK_URL"):
        application.run_webhook(listen="0.0.0.0",
                            port=int(PORT),
                            url_path=TELE_TOKEN_TEST,
                            webhook_url=os.getenv("WEBHOOK_URL") + TELE_TOKEN_TEST)
        logger.info("Application running via webhook: ", TELE_TOKEN_TEST)
        
    else:
        application.run_polling()
        logger.info("Application running via polling")