#!/usr/bin/env python
from PyInquirer import prompt, Validator, ValidationError, style_from_dict, Token
from pyfiglet import Figlet

from telethon.tl.types import UpdateShortMessage, ReplyInlineMarkup
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

from colorama import init

from sqlite3 import OperationalError

from prompt_toolkit import document

from bs4 import BeautifulSoup

import coloredlogs
import logging
import asyncio
import re
import os
import time
import requests
import sys
import json

from coin_clicker import settings

init(autoreset=True)


# Create a logger object.
logger = logging.getLogger(__name__)

MAX_REWARD_RETRIES = 5


coloredlogs.install(level='DEBUG', logger=logger,
                    fmt='%(asctime)s: %(message)s')


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


def claim_reward(code, token):
    """
    Simulates the XHR POST using the `code` and `token` parsed from the HTML, and then makes
    the reward POST. Sometimes this can save waiting 60s, other times it gets rejected by the server

    :param code:
    :param token:
    :return:
    """
    time.sleep(5)
    try:
        response = requests.request('POST', "https://doge.click/reward", headers={"User-Agent": settings.USER_AGENT},
                                    data={'code': code, 'token': token},
                                    timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as reward_exc:
        logger.error(reward_exc)
        return None, None
    text_response = response.text
    status_code = response.status_code
    return [status_code, text_response]


async def get_response_alt(client, event, url, bot_choice):
    """
    Requests `url` with requests.

    If it turns out to be telegram.me invoke a skip.
    If it is a dodge.click url with a countdown timer, attempt to grab the code/token
    and manually simulate the XHR to claim the reward rather than wait...

    :param client:
    :param event:
    :param url:
    :param bot_choice:
    :return:
    """
    try:
        response = requests.get(url, headers={"User-Agent": settings.USER_AGENT}, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as rexc:
        logger.error(rexc)
        return None, None

    if 'telegram.me' in response.url:
        # Skip it
        logger.debug('Skipping telegram.me')
        await client(GetBotCallbackAnswerRequest(
            peer=bot_choice,
            msg_id=event.message.id,
            data=event.message.reply_markup.rows[1].buttons[1].data
        ))
    elif 'doge.click' in response.url:
        logger.debug('Parse dodge-click...')
        soup = BeautifulSoup(response.text, 'html.parser')
        headbar = soup.find("div", {"id": "headbar"})
        code = headbar.get('data-code')
        token = headbar.get('data-token')
        wait_error = True
        retry_count = 0
        while wait_error is True and retry_count <= MAX_REWARD_RETRIES:
            retry_count += 1
            logger.debug(f'\t [Attempt {retry_count}/{MAX_REWARD_RETRIES}]'
                         f' Trying to claim the reward with code {code} and token {token}...')
            status_code, text = claim_reward(code, token)
            j_resp = json.loads(text)
            wait_error = 'You must wait' in j_resp['error']
            if wait_error:
                logger.debug(j_resp['error'])
                how_long = re.findall(r'\d+', j_resp['error'])[0]
                logger.debug(f'\t Waiting {how_long} seconds before retrying...')
                time.sleep(int(how_long))
            elif j_resp['reward']:
                logger.debug(f"Claimed reward of {j_resp['reward']}")
            else:
                logger.error(j_resp['error'])


def parse_input():
    """
    Get user phone number and bot choice
    :return:
    """
    # Check if already have session and existing phone number
    phone_number = None
    if os.path.exists('session'):
        existing_or_new_number = list(set([f.split('.')[0] for f in os.listdir('session')]))
        existing_or_new_number.append('New number?')
        # Options
        existing_phone_q = {'type': 'list',
                            'name': 'phone_number',
                            'message': 'Use existing phone number?',
                            'choices': existing_or_new_number
                            }
        try:
            existing_phone_result = prompt(existing_phone_q, style=style)
            phone_number = existing_phone_result['phone_number']
        except ValueError as exc:
            print(f'{exc}')
            exit()

    # We need to get the number
    if phone_number == 'New number?' or phone_number is None:
        phone_q = {'type': 'input',
                   'name': 'phone_number',
                   'message': 'What\'s your phone number?',
                   'validate': PhoneValidator
                   }
        try:
            phone_number_result = prompt(phone_q, style=style)
            phone_number = phone_number_result['phone_number']
        except ValueError as exc:
            print(f'{exc}')
            exit()

    bot_q = {'type': 'list',
             'name': 'bot_choice',
             'message': 'Which bot do you want to run?',
             'choices': ["Dogecoin_click_bot", "Litecoin_click_bot", "BCH_clickbot", "Zcash_click_bot", "Bitcoinclick_bot"],
             }
    try:
        bot_choice_result = prompt(bot_q, style=style)
        bot_choice = bot_choice_result['bot_choice']
    except ValueError as exc:
        print(f'{exc}')
        exit()

    return phone_number, bot_choice


async def main(phone_number, bot_choice):
    """
    The main loop checking for events from Telegram...

    :return:
    """
    # Session to store telegram credentials
    if not os.path.exists("session"):
        os.mkdir("session")

    # Connect to client
    try:
        client = TelegramClient(f'session/{phone_number}', settings.API_ID, settings.API_HASH)
        await client.start(phone_number)
        me = await client.get_me()
    except OperationalError as db_err:
        logger.error(f'It seems the database is locked. Kill running process or delete session dir. \n{db_err}')
        sys.exit()

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
                    # await get_response(client, event, url, bot_choice)
                    await get_response_alt(client, event, url, bot_choice)

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

    results = parse_input()
    number, choice = results

    asyncio.get_event_loop().run_until_complete(main(number, choice))
