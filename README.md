# Coin clicker

## Screenshot 

![Index](coin_clicker.png?raw=true "Dashboard 1")

The purpose of this app is to visit telegram clickbot channels and automatically visit
the websites they provide in order to earn crypto-currency, such as LTC.

## Installation

```bash
pip install coin-clicker
```

## Running

```bash
python main.py
```

You will be asked to enter your phone number and then verify the code they send you on
the first run. Next you choose which bot you wish to visit sites for. Finally, you can choose
whether to run the bot in "headless" mode or not. Headless mode means you won't see
a browser doing the visits vs seeing Chrome popup and being automated (useful for tests).

You should see the script visiting websites provided and earning crypto for you.
At some point it will run out of websites to visit and wait until more become available.

