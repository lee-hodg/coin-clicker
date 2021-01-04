#!/usr/bin/env python
from PyInquirer import prompt, Validator, ValidationError, style_from_dict, Token
from pyfiglet import Figlet

from telethon.tl.types import UpdateShortMessage, ReplyInlineMarkup
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

from prompt_toolkit import document

from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import coloredlogs
import logging
import asyncio
import re
import os
import time
import requests

from coin_clicker import settings


# Create a logger object.
logger = logging.getLogger(__name__)


coloredlogs.install(level='DEBUG', logger=logger)


class PhoneValidator(Validator):
    def validate(self, doc: document.Document) -> None:
        ok = re.match(r'^\+?\d[\d ]+\d$', doc.text)
        if not ok:
            raise ValidationError(message='Please enter a valid phone number',
                                  cursor_position=len(doc.text))


# Styles from PyInquirer prompts
style = style_from_dict({
    Token.Separator: '#cc5454',
    Token.QuestionMark: '#673ab7 bold',
    Token.Selected: '#cc5454',  # default
    Token.Pointer: '#673ab7 bold',
    Token.Instruction: '',  # default
    Token.Answer: '#f44336 bold',
    Token.Question: '',
})


questions = [
    {
        'type': 'input',
        'name': 'phone_number',
        'message': 'What\'s your phone number?',
        'validate': PhoneValidator
    },
    {
        'type': 'list',
        'name': 'bot_choice',
        'message': 'Which bot do you want to run?',
        'choices': ["Dogecoin_click_bot", "Litecoin_click_bot", "BCH_clickbot", "Zcash_click_bot", "Bitcoinclick_bot"],
    },
    {
        'type': 'confirm',
        'message': 'Do you want to run in headless mode?',
        'name': 'headless',
        'default': True,
    },
]


def claim_reward(code, token):
    """
    Simulates the XHR POST using the `code` and `token` parsed from the HTML, and then makes
    the reward POST. Sometimes this can save waiting 60s, other times it gets rejected by the server

    :param code:
    :param token:
    :return:
    """
    time.sleep(10)
    response = requests.request('POST', "https://doge.click/reward", headers={"User-Agent": settings.USER_AGENT},
                                data={'code': code, 'token': token},
                                timeout=15)
    text_response = response.text
    status_code = response.status_code
    print(f'Response status {status_code} and text {text_response}.')
    return [status_code, text_response]


async def get_response(client, event, url, bot_choice):
    """
    Requests `url` with selenium.

    If it turns out to be telegram.me invoke a skip.
    If it is a dodge.click url with a countdown timer, attempt to grab the code/token
    and manually simulate the XHR to claim the reward rather than wait...

    :param client:
    :param event:
    :param url:
    :param bot_choice:
    :return:
    """
    driver.get(url)
    if 'telegram.me' in driver.current_url:
        # Skip it
        await client(GetBotCallbackAnswerRequest(
            peer=bot_choice,
            msg_id=event.message.id,
            data=event.message.reply_markup.rows[1].buttons[1].data
        ))
    elif 'doge.click' in driver.current_url:
        headbar = driver.find_elements_by_id('headbar')[0]
        token = headbar.get_attribute('data-token')
        code = headbar.get_attribute('data-code')
        error = True
        status_code = text = None
        while error is True:
            status_code, text = claim_reward(code, token)
            error = 'You must wait' in 'text'
            time.sleep(15)
        print(f'Claimed reward with code {code} and token {token}. Result code: {status_code} and text {text}')


def parse_input():
    """
    Get user phone number and bot choice
    :return:
    """
    try:
        return prompt(questions, style=style)
    except ValueError as exc:
        print(f'{exc}')
        exit()


async def main(phone_number, bot_choice):
    """
    The main loop checking for events from Telegram...

    :return:
    """
    # Session to store telegram credentials
    if not os.path.exists("session"):
        os.mkdir("session")

    # Connect to client
    client = TelegramClient('session/' + phone_number, settings.API_ID, settings.API_HASH)
    await client.start(phone_number)
    me = await client.get_me()

    logger.debug(f'Current account: {me.first_name}({me.username})')
    logger.debug('Sending /visit command...')

    # Start command /visit
    await client.send_message(bot_choice, '/visit')

    # Start visiting the ads
    @client.on(events.NewMessage(chats=bot_choice, incoming=True))
    async def visit_adverts(event):
        """
        Handle the visit response event and go visit the website with Selenium

        :param event:
        :return:
        """
        # Check this is the visit reply event
        original_update = event.original_update
        if type(original_update) is not UpdateShortMessage:
            if hasattr(original_update.message, 'reply_markup') and type(
             original_update.message.reply_markup) is ReplyInlineMarkup:

                # Parse the URL of the website to go visit
                url = event.original_update.message.reply_markup.rows[0].buttons[0].url

                if url is not None:
                    logger.debug(f'Visiting website {url}')

                    # Visit the URL
                    await get_response(client, event, url, bot_choice)

    # Print earned money
    @client.on(events.NewMessage(chats=bot_choice, incoming=True))
    async def balance_report(event):
        """
        Handle the event telling us how much we earned by simply printing it

        :param event:
        :return:
        """
        message = event.raw_text
        if 'You earned' in message:
            logger.debug(message)

    @client.on(events.NewMessage(chats=bot_choice, incoming=True))
    async def user_skip(event):
        """
        User skipped a URL
        :param event:
        :return:
        """
        message = event.raw_text
        if 'Skipping task...' in message:
            logger.debug(message)

    @client.on(events.NewMessage(chats=bot_choice, incoming=True))
    async def no_longer_valid(event):
        """
        The URL is no longer valid

        :param event:
        :return:
        """
        message = event.raw_text
        if 'Sorry, that task is no longer valid' in message:
            logger.debug(message)
            # Init /visit to get a new one
            await client.send_message(bot_choice, '/visit')

    @client.on(events.NewMessage(chats=bot_choice, incoming=True))
    async def no_more_ads(event):
        """
        There are no more ads to visit right now

        :param event:
        :return:
        """
        message = event.raw_text
        if 'no new ads available' in message:
            logger.debug('Sorry, there are no new ads available. Waiting...')

    @client.on(events.NewMessage(chats=bot_choice, incoming=True))
    async def new_site_available(event):
        """
        After no more ads we wait and may get a message telling when there is a new site. At
        this point we start the visit process again
        :param event:
        :return:
        """
        message = event.raw_text
        if 'new site for you' in message:
            print('New site available. Visiting...')
            await client.send_message(bot_choice, '/visit')

    await client.run_until_disconnected()


if __name__ == '__main__':
    # Banner
    print(Figlet(font="slant").renderText('Coin Clicker'))

    # Options
    results = parse_input()
    number, choice, headless = results.values()

    # Set up the  webdriver
    chrome_options = Options()
    # chrome_options.add_argument("--disable-extensions")
    # chrome_options.add_argument("--disable-gpu")
    # chrome_options.add_argument("--no-sandbox") # linux only
    if headless:
        chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)

    # Start the event loop
    asyncio.get_event_loop().run_until_complete(main(number, choice))

    driver.quit()
